import os, json, logging, re, httpx, pytz
from datetime import datetime, time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes
from google_drive import upload_file_to_drive, list_folders
from google_sheets import log_to_sheet, list_sheets
from asistencias import calcular_quincena, generar_reporte_quincena, texto_resumen
from ordenes_compra import registrar_orden, texto_resumen_oc
from permisos import tiene_permiso, registrar_chat, verificar_password, es_registrado, listar_chats, ROL_OC, ROL_ADMIN, LABELS
import inventarios

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger("EstherBot")

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:1.5b")
ASISTENCIAS_SPREADSHEET_ID = os.environ["ASISTENCIAS_SPREADSHEET_ID"]
URL_PATTERN = re.compile(r'https?://[^\s]+')

(W_FOL, W_SH, W_Q, OC_E, OC_P, OC_C, S_P, S_R, I_S, I_A, I_B, I_U, I_N, I_IA, I_CI, I_TF, I_TP) = range(17)
PRODUCTOS_CIERRE = ["Café", "Leche", "Harina", "Azúcar", "Huevos"]

CHAT_PROMPT = """Eres Esther, asistente de Lily's Bakery & Coffee. Hablas español mexicano casual. Responde de forma variada, sé MUY breve (1 oración) y termina recordando que puedes ayudar con inventarios, órdenes de compra o reportes. Mensaje: {mensaje}"""

async def call_ollama(prompt: str) -> str:
    logger.info(f"🤖 IA: Iniciando consulta a Ollama (Modelo: {OLLAMA_MODEL})")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{OLLAMA_URL}/api/chat", json={"model": OLLAMA_MODEL, "stream": False, "messages": [{"role": "user", "content": prompt}]})
            logger.info("🤖 IA: Respuesta recibida exitosamente")
            return resp.json()["message"]["content"].strip()
    except Exception as e:
        logger.error(f"❌ IA ERROR: {e}")
        return "¡Dime en qué te ayudo con los inventarios o pedidos! 😊"

def store(context, **kwargs):
    logger.info(f"💾 DATA: Almacenando en user_data -> {kwargs}")
    context.user_data.update(kwargs)

def clear(context):
    logger.info("🧹 DATA: Limpiando user_data")
    context.user_data.clear()

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"🚫 FLUJO: Usuario {update.effective_user.id} canceló la operación")
    clear(context); await update.message.reply_text("❌ Cancelado."); return ConversationHandler.END

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c_id = update.effective_chat.id
    logger.info(f"🚀 COMANDO: /start recibido en chat {c_id}")
    if not es_registrado(c_id):
        logger.warning(f"⚠️ REGISTRO: Chat {c_id} no autorizado")
        await update.message.reply_text("👋 Soy Esther. Usa /setup."); return
    msg = "👋 *¡Hola! Soy Esther.*\n\n"
    if tiene_permiso(c_id, "quincena"): msg += "• /inventario\n• /inventariototal\n• /bajostock\n• /ordencompra\n• /quincena\n• /carpetas\n• /paginas\n• /chats"
    else: msg += "• /inventario\n• /ordencompra\n• /cierre"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def cmd_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"🔧 CONFIG: Iniciando /setup para {update.effective_chat.id}")
    store(context, s_id=update.effective_chat.id, s_n=update.effective_chat.title or update.effective_chat.first_name)
    await update.message.reply_text("🔧 Password:"); return S_P

async def setup_v(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("🔑 CONFIG: Verificando contraseña")
    if not verificar_password(update.message.text.strip()):
        logger.warning("❌ CONFIG: Contraseña incorrecta")
        await update.message.reply_text("❌ Mal:"); return S_P
    kb = [[InlineKeyboardButton("Staff", callback_data=f"setup_rol_{ROL_OC}")], [InlineKeyboardButton("Admin", callback_data=f"setup_rol_{ROL_ADMIN}")]]
    await update.message.reply_text("✅ Rol:", reply_markup=InlineKeyboardMarkup(kb)); return S_R

async def setup_a(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    rol = query.data.replace("setup_rol_", "")
    logger.info(f"✅ CONFIG: Registrando chat {context.user_data['s_id']} con rol {rol}")
    registrar_chat(context.user_data['s_id'], rol, context.user_data['s_n'])
    await query.edit_message_text(f"✅ Listo: {LABELS.get(rol)}."); clear(context); return ConversationHandler.END

async def cmd_inv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("📦 FLUJO: Solicitando sección de inventario")
    kb = [[InlineKeyboardButton("Cocina", callback_data="inv_cocina")], [InlineKeyboardButton("Cafetería", callback_data="inv_cafeteria")]]
    await update.message.reply_text("📦 ¿Sección?", reply_markup=InlineKeyboardMarkup(kb)); return I_S

async def inv_s(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    seccion = query.data.replace("inv_", "")
    logger.info(f"📍 FLUJO: Sección seleccionada -> {seccion}")
    store(context, inv_s=seccion)
    kb = [[InlineKeyboardButton("🔄 Actualizar", callback_data="act_ex"), InlineKeyboardButton("➕ Nuevo", callback_data="act_nu")]]
    await query.edit_message_text(f"📍 {seccion.upper()}:", reply_markup=InlineKeyboardMarkup(kb)); return I_A

async def inv_b(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("🔍 FLUJO: Esperando nombre para búsqueda")
    await update.callback_query.answer(); await update.callback_query.edit_message_text("🔍 Nombre:"); return I_B

async def inv_pb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    busqueda = update.message.text.strip()
    logger.info(f"🔍 BUSQUEDA: Consultando '{busqueda}' en {context.user_data['inv_s']}")
    art = inventarios.buscar_articulo(context.user_data['inv_s'], busqueda)
    if art:
        logger.info(f"🎯 BUSQUEDA: Artículo encontrado en fila {art['fila']}")
        store(context, inv_f=art['fila'])
        await update.message.reply_text(f"✅ *{art['nombre']}*\nActual: {art['cantidad_actual']}\n¿Nueva?"); return I_U
    logger.warning("❓ BUSQUEDA: Artículo no encontrado")
    await update.message.reply_text("❌ No hallado."); return ConversationHandler.END

async def inv_f(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"🔄 ACTUALIZACION: Procesando nueva cantidad '{update.message.text}'")
    inventarios.actualizar_cantidad(context.user_data['inv_s'], context.user_data['inv_f'], update.message.text.strip())
    await update.message.reply_text("✅ Hecho."); clear(context); return ConversationHandler.END

async def inv_in(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("➕ FLUJO: Esperando datos para nuevo artículo")
    await update.callback_query.answer(); await update.callback_query.edit_message_text("📝 Envía: `Art, Marca, Cont, Cant, Uni, Cat, Notas, Min` "); return I_N

async def inv_pn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"📥 INPUT: Recibidos datos de nuevo artículo -> {update.message.text}")
    try:
        p = [x.strip() for x in update.message.text.split(",")]
        d = {"articulo": p[0], "marca": p[1], "contenido": p[2], "cantidad": p[3], "unidad": p[4], "categoria": p[5], "notas": p[6] if len(p)>6 else "", "minimo": p[7] if len(p)>7 else "0"}
        inventarios.agregar_nuevo_articulo(context.user_data['inv_s'], d); await update.message.reply_text("✅ Agregado.")
        logger.info("✅ FLUJO: Artículo agregado correctamente")
    except Exception as e:
        logger.error(f"❌ ERROR REGISTRO: {e}")
        await update.message.reply_text("⚠️ Error formato."); return I_N
    clear(context); return ConversationHandler.END

async def cmd_it(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("📋 FLUJO: Iniciando listado total de inventario")
    kb = [[InlineKeyboardButton("🆕 Últimos", callback_data="tot_todo")], [InlineKeyboardButton("⏰ Viejos (+5d)", callback_data="tot_viejos")], [InlineKeyboardButton("🚨 Mínimos", callback_data="tot_minimos")]]
    await update.message.reply_text("📋 Filtro:", reply_markup=InlineKeyboardMarkup(kb)); return I_TF

async def it_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    filtro = query.data.replace("tot_", "")
    logger.info(f"📋 FLUJO: Aplicando filtro '{filtro}' al listado total")
    store(context, l_t=inventarios.obtener_total_paginado(filtro), p_t=0); return await send_p(query, context)

async def send_p(query, context):
    items, pag = context.user_data['l_t'], context.user_data['p_t']
    ini, fin = pag * 10, (pag + 1) * 10
    bloque = items[ini:fin]
    logger.info(f"📄 PAGINACION: Enviando página {pag+1} (Artículos {ini} a {fin-1})")
    if not bloque:
        logger.info("📄 PAGINACION: No hay más artículos para mostrar")
        await query.edit_message_text("Es todo. 😊"); return ConversationHandler.END
    txt = f"📋 *Inventario (Pág {pag+1})*\n\n"
    for i in bloque: txt += f"• *{i['nombre']}*: `{i['cantidad']}` ({i['seccion']})\n"
    kb = []
    if fin < len(items): kb.append(InlineKeyboardButton("Sig ➡️", callback_data="pag_next"))
    if pag > 0: kb.append(InlineKeyboardButton("⬅️ Ant", callback_data="pag_prev"))
    await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([kb]), parse_mode="Markdown"); return I_TP

async def pag_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    context.user_data['p_t'] += 1 if query.data == "pag_next" else -1
    logger.info(f"📄 PAGINACION: Cambiando a página {context.user_data['p_t']+1}")
    return await send_p(query, context)

async def cmd_oc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"📋 FLUJO: Iniciando Orden de Compra por {update.effective_user.id}")
    if not tiene_permiso(update.effective_chat.id, "orden_compra"):
        logger.warning("❌ PERMISO: Denegado para Orden de Compra")
        return
    store(context, oc_p=[], oc_e=""); await update.message.reply_text("📋 ¿Encargada?"); return OC_E

async def oc_e(update: Update, context: ContextTypes.DEFAULT_TYPE):
    store(context, oc_e=update.message.text.strip()); await update.message.reply_text("✅ Productos (escribe 'listo'):"); return OC_P

async def oc_p(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if txt.lower() in ["listo", "fin"]:
        logger.info(f"✅ FLUJO: Lista de OC finalizada con {len(context.user_data['oc_p'])} productos")
        res = texto_resumen_oc(context.user_data['oc_p'], context.user_data['oc_e'])
        await update.message.reply_text(f"{res}\n¿Guardar?", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Sí", callback_data="oc_save")]])); return OC_C
    context.user_data['oc_p'].append({"producto": txt, "cantidad": "1", "marca": ""})
    return OC_P

async def oc_c(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    logger.info("💾 OC: Guardando orden de compra en Google Sheets")
    id_o = registrar_orden(context.user_data['oc_p'], context.user_data['oc_e'])
    await query.edit_message_text(f"✅ Folio: `{id_o}`"); clear(context); return ConversationHandler.END

async def cmd_q(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"📅 FLUJO: Iniciando reporte de Quincena por {update.effective_user.id}")
    if not tiene_permiso(update.effective_chat.id, "quincena"):
        logger.warning("❌ PERMISO: Denegado para Quincenas")
        return
    await update.message.reply_text("📅 Rango: `DD/MM/AAAA - DD/MM/AAAA` "); return W_Q

async def q_f(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"📅 FLUJO: Procesando fechas de quincena -> {update.message.text}")
    try:
        p = update.message.text.split("-")
        ini, fin = datetime.strptime(p[0].strip(), "%d/%m/%Y"), datetime.strptime(p[1].strip(), "%d/%m/%Y")
        res = calcular_quincena(ini, fin)
        await update.message.reply_text(texto_resumen(res, update.message.text), parse_mode="Markdown")
        logger.info("✅ QUINCENA: Reporte generado exitosamente")
    except Exception as e:
        logger.error(f"❌ ERROR QUINCENA: {e}")
        await update.message.reply_text("❌ Formato mal."); return ConversationHandler.END

async def h_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not es_registrado(update.effective_chat.id): return
    txt = update.message.text
    logger.info(f"📥 INPUT: Mensaje de {update.effective_user.first_name} (@{update.effective_chat.id}): '{txt}'")
    txt_l = txt.lower()
    if any(w in txt_l for w in ["ayuda", "ayúdame", "puedes hacer"]):
        logger.info("🚩 FLAG: Detectada intención de AYUDA")
        return await start(update, context)
    if any(w in txt_l for w in ["cuántas", "tienes", "hay"]):
        logger.info("🚩 FLAG: Detectada intención de BUSQUEDA NATURAL")
        p = txt_l.replace("cuántas","").replace("tienes","").replace("hay","").replace("?","").replace("esther","").replace("cocoas","cocoa").strip()
        logger.info(f"🔍 BUSQUEDA: Intentando localizar stock para '{p}'")
        art = inventarios.buscar_articulo("cocina", p) or inventarios.buscar_articulo("cafeteria", p)
        if art:
            logger.info("🎯 RESULTADO: Stock encontrado para respuesta rápida")
            await update.message.reply_text(f"De *{art['nombre']}* hay `{art['cantidad_actual']}`. 😊")
        else:
            logger.warning("❓ RESULTADO: Sin stock para respuesta rápida")
            await update.message.reply_text(f"No hallé '{p}'.")
        return
    logger.info("🚩 FLAG: Procesando como CHAT GENERAL con Ollama")
    resp = await call_ollama(CHAT_PROMPT.format(mensaje=txt))
    await update.message.reply_text(resp)

def main():
    logger.info("🚀 SISTEMA: Iniciando Esther-Bot en Telegram...")
    app = Application.builder().token(BOT_TOKEN).build()
    
    setup_conv = ConversationHandler(
        entry_points=[CommandHandler("setup", cmd_setup)], 
        states={S_P: [MessageHandler(filters.TEXT & ~filters.COMMAND, setup_v)], S_R: [CallbackQueryHandler(setup_a, pattern="^setup_")]}, 
        fallbacks=[CommandHandler("cancelar", cancel)]
    )
    
    inv_conv = ConversationHandler(
        entry_points=[CommandHandler("inventario", cmd_inv), CommandHandler("inventariototal", cmd_it)], 
        states={
            I_S: [CallbackQueryHandler(inv_s, pattern="^inv_")], 
            I_A: [CallbackQueryHandler(inv_b, pattern="act_ex"), CallbackQueryHandler(inv_in, pattern="act_nu")], 
            I_B: [MessageHandler(filters.TEXT & ~filters.COMMAND, inv_pb)], 
            I_U: [MessageHandler(filters.TEXT & ~filters.COMMAND, inv_f)], 
            I_N: [MessageHandler(filters.TEXT & ~filters.COMMAND, inv_pn)], 
            I_TF: [CallbackQueryHandler(it_cb, pattern="^tot_")], 
            I_TP: [CallbackQueryHandler(pag_cb, pattern="^pag_")]
        }, 
        fallbacks=[CommandHandler("cancelar", cancel)]
    )
    
    oc_conv = ConversationHandler(
        entry_points=[CommandHandler("ordencompra", cmd_oc)], 
        states={OC_E: [MessageHandler(filters.TEXT & ~filters.COMMAND, oc_e)], OC_P: [MessageHandler(filters.TEXT & ~filters.COMMAND, oc_p)], OC_C: [CallbackQueryHandler(oc_c, pattern="oc_save")]}, 
        fallbacks=[CommandHandler("cancelar", cancel)]
    )
    
    q_conv = ConversationHandler(
        entry_points=[CommandHandler("quincena", cmd_q)], 
        states={W_Q: [MessageHandler(filters.TEXT & ~filters.COMMAND, q_f)]}, 
        fallbacks=[CommandHandler("cancelar", cancel)]
    )

    app.add_handler(setup_conv); app.add_handler(inv_conv); app.add_handler(oc_conv); app.add_handler(q_conv)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, h_text))
    
    logger.info("✅ SISTEMA: Bot operando y escuchando peticiones")
    app.run_polling()

if __name__ == "__main__": main()