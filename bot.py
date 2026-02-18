import os
import json
import logging
import re
import httpx
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, filters,
    ContextTypes
)
from google_drive import upload_file_to_drive, list_folders, create_folder, list_files_in_folder
from google_sheets import log_to_sheet, list_sheets, create_sheet

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
URL_PATTERN = re.compile(r'https?://[^\s]+')

(
    WAITING_FOLDER_CHOICE,
    WAITING_NEW_FOLDER_NAME,
    WAITING_EXISTING_FOLDER_NAME,
    WAITING_SHEET_CHOICE,
    WAITING_NEW_SHEET_NAME,
) = range(5)

INTENT_PROMPT = """Eres Esther, asistente de Lily's Bakery & Coffee.
Analiza el mensaje y responde SOLO con un JSON válido, sin texto extra.

Intenciones posibles:
- "chat": saludo, agradecimiento, pregunta general, despedida, respuesta corta como "no", "ok", "bye"
- "ver_carpetas": quiere ver las carpetas de Drive
- "ver_paginas": quiere ver las páginas del Sheet
- "ver_archivos": quiere ver archivos de una carpeta o de Drive en general
- "nueva_pagina": quiere crear una página nueva en el Sheet
- "subir_general": quiere subir archivo a carpeta general
- "subir_carpeta": menciona una carpeta específica donde subir

Ejemplos:
{{"intencion": "chat", "parametro": null}}
{{"intencion": "ver_carpetas", "parametro": null}}
{{"intencion": "ver_archivos", "parametro": null}}
{{"intencion": "ver_archivos", "parametro": "Recetas"}}
{{"intencion": "nueva_pagina", "parametro": "Proveedores"}}
{{"intencion": "subir_carpeta", "parametro": "Recetas"}}

Mensaje del usuario: {mensaje}"""

CHAT_PROMPT = """Eres Esther, asistente simpática de Lily's Bakery & Coffee.
Hablas en español mexicano muy casual y natural, como una compañera de trabajo.
Eres breve (máximo 1 oración). No menciones que eres IA. No preguntes cómo ayudar.

Ejemplos de cómo responder:
- "hola" → "¡Hola! 👋"
- "no" → "¡Okey, aquí estoy si me necesitas!"
- "gracias" → "¡De nada! 😊"
- "gracias esther" → "¡Con mucho gusto! 🌸"
- "bye" → "¡Hasta luego! 👋"
- "ok" → "¡Perfecto!"

Mensaje: {mensaje}"""


# ─── Ollama ──────────────────────────────────────────────────────────────────

async def call_ollama(prompt: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": OLLAMA_MODEL,
                    "stream": False,
                    "messages": [{"role": "user", "content": prompt}]
                }
            )
            return resp.json()["message"]["content"].strip()
    except Exception as e:
        logger.warning(f"Ollama error: {e}")
        return ""


async def detect_intent(text: str) -> dict:
    prompt = INTENT_PROMPT.format(mensaje=text)
    raw = await call_ollama(prompt)
    try:
        match = re.search(r'\{.*?\}', raw, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception as e:
        logger.warning(f"Intent parse error: {e} — raw: {raw}")
    return {"intencion": "chat", "parametro": None}


async def chat_response(text: str) -> str:
    prompt = CHAT_PROMPT.format(mensaje=text)
    resp = await call_ollama(prompt)
    return resp or "¡Aquí estoy! 😊"


# ─── Helpers ─────────────────────────────────────────────────────────────────

def store(context, **kwargs):
    context.user_data.update(kwargs)

def clear(context):
    context.user_data.clear()


# ─── /start ──────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 ¡Hola! Soy *Esther*, tu asistente de Lily's Bakery.\n\n"
        "Puedes hablarme natural, por ejemplo:\n"
        "• _\"súbelo a la carpeta Recetas\"_\n"
        "• _\"¿qué archivos tengo en Proveedores?\"_\n"
        "• _\"crea una página llamada Gastos\"_\n\n"
        "Comandos:\n"
        "/carpetas — ver carpetas en Drive\n"
        "/paginas — ver páginas del Sheet\n"
        "/nuevapagina — crear nueva página",
        parse_mode="Markdown"
    )


# ─── Comandos ────────────────────────────────────────────────────────────────

async def cmd_carpetas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    folders = list_folders()
    if not folders:
        await update.message.reply_text("📂 No hay carpetas en Drive todavía.")
        return
    lines = "\n".join(f"• {f['name']}" for f in folders)
    await update.message.reply_text(f"📂 *Carpetas en Drive:*\n{lines}", parse_mode="Markdown")


async def cmd_paginas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sheets = list_sheets()
    lines = "\n".join(f"• {s}" for s in sheets)
    await update.message.reply_text(f"📋 *Páginas en Google Sheet:*\n{lines}", parse_mode="Markdown")


async def cmd_nueva_pagina(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📋 ¿Cómo se llamará la nueva página?")
    return WAITING_NEW_SHEET_NAME


async def receive_new_sheet_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    try:
        create_sheet(name)
        await update.message.reply_text(f"✅ Página *{name}* creada.", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
    return ConversationHandler.END


# ─── TEXTO con detección de intención ────────────────────────────────────────

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    urls = URL_PATTERN.findall(text)

    if urls:
        store(context, urls=urls, nota=text, usuario=update.message.from_user.first_name)
        sheets = list_sheets()
        keyboard = [[InlineKeyboardButton(s, callback_data=f"sheet_{s}")] for s in sheets]
        keyboard.append([InlineKeyboardButton("✨ Nueva página", callback_data="sheet_new")])
        await update.message.reply_text(
            f"🔗 Encontré {len(urls)} link(s).\n¿En qué página del Sheet los registro?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return WAITING_SHEET_CHOICE

    await update.message.chat.send_action("typing")
    intent = await detect_intent(text)
    intencion = intent.get("intencion", "chat")
    parametro = intent.get("parametro")

    if intencion == "ver_carpetas":
        folders = list_folders()
        if not folders:
            await update.message.reply_text("📂 No tienes carpetas en Drive todavía. ¿Quieres crear una?")
        else:
            lines = "\n".join(f"• {f['name']}" for f in folders)
            await update.message.reply_text(f"📂 *Tus carpetas en Drive:*\n{lines}", parse_mode="Markdown")

    elif intencion == "ver_paginas":
        sheets = list_sheets()
        lines = "\n".join(f"• {s}" for s in sheets)
        await update.message.reply_text(f"📋 *Páginas en tu Sheet:*\n{lines}", parse_mode="Markdown")

    elif intencion == "ver_archivos":
        folder_id = None
        label = "Drive"
        if parametro:
            folders = list_folders()
            match = next((f for f in folders if f["name"].lower() == parametro.lower()), None)
            if match:
                folder_id = match["id"]
                label = parametro
            else:
                await update.message.reply_text(f"📂 No encontré la carpeta *{parametro}*.", parse_mode="Markdown")
                return ConversationHandler.END
        files = list_files_in_folder(folder_id)
        if not files:
            await update.message.reply_text(f"📂 No hay archivos en *{label}* todavía.", parse_mode="Markdown")
        else:
            lines = "\n".join(
                f"• [{f['name']}](https://drive.google.com/file/d/{f['id']}/view)"
                for f in files[:20]
            )
            await update.message.reply_text(
                f"📂 *Archivos en {label}:*\n{lines}",
                parse_mode="Markdown"
            )

    elif intencion == "nueva_pagina":
        if parametro:
            try:
                create_sheet(parametro)
                await update.message.reply_text(f"✅ Página *{parametro}* creada.", parse_mode="Markdown")
            except Exception as e:
                await update.message.reply_text(f"❌ Error: {e}")
        else:
            await update.message.reply_text("📋 ¿Cómo se llamará la nueva página?")
            return WAITING_NEW_SHEET_NAME

    elif intencion == "subir_carpeta" and parametro:
        store(context, carpeta_preferida=parametro)
        await update.message.reply_text(
            f"📁 Listo, el próximo archivo lo subiré a *{parametro}*. ¡Mándamelo!",
            parse_mode="Markdown"
        )

    elif intencion == "subir_general":
        store(context, carpeta_preferida=None)
        await update.message.reply_text("📁 Listo, el próximo archivo lo subiré a la carpeta general.")

    else:
        respuesta = await chat_response(text)
        await update.message.reply_text(respuesta)

    return ConversationHandler.END


# ─── ARCHIVOS ────────────────────────────────────────────────────────────────

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message

    if message.document:
        file = message.document
        file_name = file.file_name
        mime_type = file.mime_type or "application/octet-stream"
    elif message.photo:
        file = message.photo[-1]
        file_name = f"foto_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        mime_type = "image/jpeg"
    elif message.video:
        file = message.video
        file_name = file.file_name or f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        mime_type = file.mime_type or "video/mp4"
    elif message.audio:
        file = message.audio
        file_name = file.file_name or f"audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
        mime_type = file.mime_type or "audio/mpeg"
    else:
        await message.reply_text("❌ Tipo de archivo no soportado.")
        return ConversationHandler.END

    store(context,
          file_id=file.file_id,
          file_name=file_name,
          mime_type=mime_type,
          caption=message.caption or "",
          usuario=message.from_user.first_name)

    carpeta_preferida = context.user_data.get("carpeta_preferida", "NO_PREFERENCE")
    if carpeta_preferida != "NO_PREFERENCE":
        folder_id = None
        folder_label = "carpeta general"
        if carpeta_preferida:
            folders = list_folders()
            match = next((f for f in folders if f["name"].lower() == carpeta_preferida.lower()), None)
            if match:
                folder_id = match["id"]
                folder_label = carpeta_preferida
            else:
                folder_id = create_folder(carpeta_preferida)
                folder_label = f"{carpeta_preferida} (nueva)"
        await message.reply_text(f"⏳ Subiendo a *{folder_label}*...", parse_mode="Markdown")
        await do_upload(context, message, folder_id=folder_id)
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("📁 Carpeta general", callback_data="folder_general")],
        [InlineKeyboardButton("✨ Nueva carpeta", callback_data="folder_new")],
        [InlineKeyboardButton("📂 Carpeta existente", callback_data="folder_existing")],
    ]
    await message.reply_text(
        f"📎 *{file_name}*\n\n¿Dónde lo guardo en Drive?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return WAITING_FOLDER_CHOICE


async def folder_choice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data

    if choice == "folder_general":
        await query.edit_message_text("⏳ Subiendo a la carpeta general...")
        await do_upload(context, query.message, folder_id=None)
        return ConversationHandler.END
    elif choice == "folder_new":
        await query.edit_message_text("📁 ¿Cómo se llamará la nueva carpeta?")
        return WAITING_NEW_FOLDER_NAME
    elif choice == "folder_existing":
        folders = list_folders()
        if not folders:
            await query.edit_message_text("No hay carpetas. ¿Cómo se llamará la nueva?")
            return WAITING_NEW_FOLDER_NAME
        keyboard = [[InlineKeyboardButton(f['name'], callback_data=f"fid_{f['id']}")] for f in folders]
        await query.edit_message_text("📂 Selecciona la carpeta:", reply_markup=InlineKeyboardMarkup(keyboard))
        return WAITING_EXISTING_FOLDER_NAME


async def receive_new_folder_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    await update.message.reply_text(f"⏳ Creando carpeta *{name}*...", parse_mode="Markdown")
    folder_id = create_folder(name)
    await do_upload(context, update.message, folder_id=folder_id)
    return ConversationHandler.END


async def existing_folder_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    folder_id = query.data.replace("fid_", "")
    await query.edit_message_text("⏳ Subiendo archivo...")
    await do_upload(context, query.message, folder_id=folder_id)
    return ConversationHandler.END


async def do_upload(context, message, folder_id):
    d = context.user_data
    try:
        tg_file = await context.bot.get_file(d["file_id"])
        file_bytes = await tg_file.download_as_bytearray()
        drive_link = upload_file_to_drive(file_bytes, d["file_name"], d["mime_type"], folder_id=folder_id)
        log_to_sheet(tipo="Archivo", nombre=d["file_name"], link=drive_link,
                     mime=d["mime_type"], nota=d["caption"], usuario=d["usuario"],
                     sheet_name="Registro")
        await message.reply_text(
            f"✅ *{d['file_name']}* subido a Drive.\n🔗 [Ver archivo]({drive_link})",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error subiendo: {e}")
        await message.reply_text(f"❌ Error: {e}")
    finally:
        clear(context)


# ─── LINKS ───────────────────────────────────────────────────────────────────

async def sheet_choice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data

    if choice == "sheet_new":
        await query.edit_message_text("📋 ¿Cómo se llamará la nueva página?")
        return WAITING_NEW_SHEET_NAME
    else:
        sheet_name = choice.replace("sheet_", "")
        await query.edit_message_text(f"⏳ Guardando en *{sheet_name}*...", parse_mode="Markdown")
        await do_log_links(context, query.message, sheet_name)
        return ConversationHandler.END


async def receive_new_sheet_for_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    try:
        create_sheet(name)
        await do_log_links(context, update.message, name)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
    return ConversationHandler.END


async def do_log_links(context, message, sheet_name):
    d = context.user_data
    results = []
    for url in d["urls"]:
        try:
            log_to_sheet(tipo="Link", nombre=url[:80], link=url,
                         mime="URL", nota=d["nota"].replace(url, "").strip(),
                         usuario=d["usuario"], sheet_name=sheet_name)
            results.append(f"✅ Link registrado en *{sheet_name}*")
        except Exception as e:
            results.append(f"❌ Error: {e}")
    await message.reply_text("\n".join(results), parse_mode="Markdown")
    clear(context)


# ─── Cancelar ────────────────────────────────────────────────────────────────

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear(context)
    await update.message.reply_text("❌ Operación cancelada.")
    return ConversationHandler.END


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    file_conv = ConversationHandler(
        entry_points=[MessageHandler(
            filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO,
            handle_file
        )],
        states={
            WAITING_FOLDER_CHOICE: [CallbackQueryHandler(folder_choice_callback, pattern="^folder_")],
            WAITING_NEW_FOLDER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_new_folder_name)],
            WAITING_EXISTING_FOLDER_NAME: [CallbackQueryHandler(existing_folder_callback, pattern="^fid_")],
        },
        fallbacks=[CommandHandler("cancelar", cancel)],
        per_user=True,
        per_chat=False
    )

    link_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)],
        states={
            WAITING_SHEET_CHOICE: [CallbackQueryHandler(sheet_choice_callback, pattern="^sheet_")],
            WAITING_NEW_SHEET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_new_sheet_for_link)],
        },
        fallbacks=[CommandHandler("cancelar", cancel)],
        per_user=True,
        per_chat=False
    )

    new_page_conv = ConversationHandler(
        entry_points=[CommandHandler("nuevapagina", cmd_nueva_pagina)],
        states={
            WAITING_NEW_SHEET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_new_sheet_name)],
        },
        fallbacks=[CommandHandler("cancelar", cancel)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("carpetas", cmd_carpetas))
    app.add_handler(CommandHandler("paginas", cmd_paginas))
    app.add_handler(new_page_conv)
    app.add_handler(file_conv)
    app.add_handler(link_conv)

    logger.info("🤖 Esther iniciada...")
    app.run_polling()


if __name__ == "__main__":
    main()