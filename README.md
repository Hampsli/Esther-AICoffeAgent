# 🤖 Bot de Telegram → Google Drive + Google Sheets

Bot personal para recibir archivos y links en Telegram, subirlos automáticamente
a Google Drive y registrarlos en Google Sheets. Corre en Docker en tu PC.

---

## 📋 Requisitos previos

- Docker Desktop instalado ([docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop))
- Una cuenta de Google
- Cuenta de Telegram

---

## 🚀 Paso 1 – Crear el bot en Telegram

1. Abre Telegram y busca **@BotFather**
2. Escribe `/newbot`
3. Ponle un nombre (ej: "Mi Bot de Archivos")
4. Ponle un username que termine en `bot` (ej: `mis_archivos_bot`)
5. BotFather te dará un **token** → guárdalo, lo necesitarás después

---

## ☁️ Paso 2 – Configurar Google Cloud (una sola vez)

### 2.1 Crear proyecto y habilitar APIs

1. Ve a [console.cloud.google.com](https://console.cloud.google.com)
2. Crea un proyecto nuevo (ej: "bot-telegram")
3. En el menú lateral → **APIs y Servicios** → **Biblioteca**
4. Busca y habilita:
   - ✅ **Google Drive API**
   - ✅ **Google Sheets API**

### 2.2 Crear cuenta de servicio

1. Ve a **APIs y Servicios** → **Credenciales**
2. Clic en **+ Crear Credenciales** → **Cuenta de servicio**
3. Nombre: `bot-telegram-sa` → Crear y continuar → Listo
4. Clic en la cuenta de servicio creada → pestaña **Claves**
5. **Agregar clave** → **Crear nueva clave** → **JSON**
6. Se descargará un archivo JSON → **renómbralo a `credentials.json`**
7. **Cópialo a la carpeta del proyecto** (junto a `docker-compose.yml`)

### 2.3 Anotar el email de la cuenta de servicio

En la lista de cuentas de servicio verás un email como:
`bot-telegram-sa@tu-proyecto.iam.gserviceaccount.com`

Guárdalo, lo necesitas en el siguiente paso.

---

## 📁 Paso 3 – Preparar Google Drive y Google Sheets

### Carpeta en Drive

1. Abre [drive.google.com](https://drive.google.com)
2. Crea una carpeta nueva (ej: "Archivos Bot Telegram")
3. Clic derecho en la carpeta → **Compartir**
4. Pega el email de la cuenta de servicio → rol **Editor** → Enviar
5. Abre la carpeta y copia el **ID de la URL**:
   - URL: `drive.google.com/drive/folders/`**`ESTE_ES_EL_ID`**

### Hoja de Google Sheets

1. Ve a [sheets.google.com](https://sheets.google.com) y crea una hoja nueva
2. Nómbrala como quieras (ej: "Registro Bot")
3. En la hoja, asegúrate de que la primera pestaña se llame **`Registro`**
   (doble clic en la pestaña abajo para renombrarla)
4. Clic en **Compartir** (arriba a la derecha)
5. Pega el email de la cuenta de servicio → rol **Editor** → Enviar
6. Copia el **ID del Spreadsheet** de la URL:
   - URL: `docs.google.com/spreadsheets/d/`**`ESTE_ES_EL_ID`**`/edit`

---

## ⚙️ Paso 4 – Configurar variables de entorno

1. En la carpeta del proyecto, copia el archivo de ejemplo:
   ```bash
   cp .env.example .env
   ```

2. Abre `.env` con cualquier editor de texto y rellena los valores:
   ```
   TELEGRAM_BOT_TOKEN=el_token_que_te_dio_botfather
   SPREADSHEET_ID=el_id_de_tu_google_sheet
   DRIVE_FOLDER_ID=el_id_de_tu_carpeta_de_drive
   ```

---

## 🐳 Paso 5 – Construir y correr con Docker

Abre una terminal en la carpeta del proyecto y ejecuta:

```bash
# Construir la imagen (solo la primera vez o cuando cambies código)
docker compose build

# Iniciar el bot
docker compose up -d

# Ver los logs en tiempo real
docker compose logs -f

# Detener el bot
docker compose down
```

---

## 📅 Uso diario (encender y apagar)

Como configuramos `restart: "no"`, el bot **no arranca solo** cuando enciendes la PC.
Tú decides cuándo corre:

```bash
# Encender (al empezar tu jornada)
docker compose up -d

# Apagar (al terminar tu jornada)
docker compose down
```

**Tip:** Puedes crear un acceso directo o script para hacerlo con doble clic.

### Windows – script para encender (iniciar_bot.bat)
```bat
@echo off
cd /d "C:\ruta\a\tu\carpeta\telegram-bot"
docker compose up -d
echo Bot iniciado ✅
pause
```

### Windows – script para apagar (detener_bot.bat)
```bat
@echo off
cd /d "C:\ruta\a\tu\carpeta\telegram-bot"
docker compose down
echo Bot detenido ✅
pause
```

### Mac/Linux – script (iniciar_bot.sh)
```bash
#!/bin/bash
cd ~/telegram-bot
docker compose up -d
echo "Bot iniciado ✅"
```

---

## 📊 ¿Qué registra en Google Sheets?

Cada archivo o link genera una fila con:

| Fecha | Hora | Usuario | Tipo | Nombre / URL | Tipo MIME | Link en Drive | Nota |
|-------|------|---------|------|--------------|-----------|---------------|------|
| 17/02/2026 | 10:35:22 | Juan | Archivo | reporte.pdf | application/pdf | https://drive... | |
| 17/02/2026 | 10:36:01 | Juan | Link | https://ejemplo.com | URL | https://drive... | revisar esto |

---

## 📁 Estructura del proyecto

```
telegram-bot/
├── bot.py              # Lógica principal del bot
├── google_drive.py     # Subida de archivos a Drive
├── google_sheets.py    # Registro en Sheets
├── requirements.txt    # Dependencias Python
├── Dockerfile          # Imagen Docker
├── docker-compose.yml  # Configuración del contenedor
├── .env                # Tus credenciales (¡no compartir!)
├── .env.example        # Plantilla de variables
├── credentials.json    # Credenciales Google (¡no compartir!)
└── .gitignore          # Ignora archivos sensibles
```

---

## 🛠️ Solución de problemas

**El bot no responde:**
```bash
docker compose logs -f   # Ver errores en tiempo real
```

**Error de credenciales de Google:**
- Verifica que `credentials.json` está en la carpeta del proyecto
- Verifica que compartiste Drive y Sheets con el email de la cuenta de servicio

**Error "SPREADSHEET_ID not set":**
- Verifica que tu archivo `.env` tiene los valores correctos (sin comillas extra)

**Quiero que el bot arranque solo con Windows:**
- En Docker Desktop → Settings → General → activa "Start Docker Desktop when you log in"
- Cambia `restart: "no"` a `restart: "unless-stopped"` en `docker-compose.yml`
- Ejecuta `docker compose up -d` una vez y ya no necesitas volver a hacerlo

---

## 🔒 Seguridad

- Nunca subas `.env` ni `credentials.json` a GitHub
- El `.gitignore` ya los excluye por defecto
- Los archivos en Drive son accesibles "con el link" (no públicos en búsquedas)
