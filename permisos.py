import json
import os
import logging

logger = logging.getLogger(__name__)

CONFIG_PATH = os.environ.get("CONFIG_PATH", "/app/config.json")

# Roles
ROL_OC = "ordenes_compra"
ROL_ADMIN = "admin"

PERMISOS = {
    ROL_OC: {
        "orden_compra",
        "chat",
    },
    ROL_ADMIN: {
        "orden_compra",
        "chat",
        "ver_carpetas",
        "ver_paginas",
        "ver_archivos",
        "nueva_pagina",
        "subir_general",
        "subir_carpeta",
        "quincena",
        "setup",
        "cambiar_password",
    }
}

LABELS = {
    ROL_OC:    "📋 Órdenes de Compra",
    ROL_ADMIN: "👑 Admin (acceso completo)",
}

DEFAULT_PASSWORD = "lilys2024"


def _cargar() -> dict:
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _guardar(config: dict):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


# ─── Password ────────────────────────────────────────────────────────────────

def obtener_password() -> str:
    config = _cargar()
    return config.get("_password", DEFAULT_PASSWORD)


def cambiar_password(nueva: str):
    config = _cargar()
    config["_password"] = nueva.strip()
    _guardar(config)
    logger.info("Password actualizado")


def verificar_password(password: str) -> bool:
    return password.strip() == obtener_password()


# ─── Chats ───────────────────────────────────────────────────────────────────

def registrar_chat(chat_id: int, rol: str, nombre: str = ""):
    config = _cargar()
    config[str(chat_id)] = {"rol": rol, "nombre": nombre}
    _guardar(config)
    logger.info(f"Chat {chat_id} ({nombre}) → {rol}")


def obtener_rol(chat_id: int) -> str | None:
    config = _cargar()
    entry = config.get(str(chat_id))
    return entry["rol"] if entry else None


def tiene_permiso(chat_id: int, accion: str) -> bool:
    rol = obtener_rol(chat_id)
    if rol is None:
        return False
    return accion in PERMISOS.get(rol, set())


def es_registrado(chat_id: int) -> bool:
    config = _cargar()
    return str(chat_id) in config


def listar_chats() -> list:
    config = _cargar()
    return [
        {
            "chat_id": cid,
            "nombre": datos.get("nombre", "Sin nombre"),
            "rol": datos.get("rol", "?"),
            "label": LABELS.get(datos.get("rol", ""), "?")
        }
        for cid, datos in config.items()
        if not cid.startswith("_")  # excluir _password y otros metadatos
    ]