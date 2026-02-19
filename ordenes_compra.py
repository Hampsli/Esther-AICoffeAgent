import os
import logging
from datetime import datetime
from googleapiclient.discovery import build
from google_drive import _get_creds

logger = logging.getLogger(__name__)

# Variables de entorno
OC_SPREADSHEET_ID = os.environ["OC_SPREADSHEET_ID"]
OC_SHEET = "ordenes de compras v2"

HEADERS_OC = [
    "ID Orden", "Fecha de Orden", "Encargada de compras",
    "Producto", "Cantidad", "Marca"
]

def _get_service():
    return build("sheets", "v4", credentials=_get_creds())

def _ensure_headers(service):
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=OC_SPREADSHEET_ID,
            range=f"{OC_SHEET}!A1:F1"
        ).execute()
        if not result.get("values"):
            service.spreadsheets().values().update(
                spreadsheetId=OC_SPREADSHEET_ID,
                range=f"{OC_SHEET}!A1",
                valueInputOption="RAW",
                body={"values": [HEADERS_OC]}
            ).execute()
    except Exception as e:
        logger.error(f"Error asegurando headers: {e}")

def generar_id_orden() -> str:
    meses = {
        1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
        7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"
    }
    now = datetime.now()
    mes, año = meses[now.month], str(now.year)[2:]
    service = _get_service()
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=OC_SPREADSHEET_ID,
            range=f"{OC_SHEET}!A:A"
        ).execute()
        ids = [r[0] for r in result.get("values", [])
               if r and mes.lower() in str(r[0]).lower()]
        num = str(len(ids) + 1).zfill(2)
    except Exception:
        num = "01"
    return f"{mes}{año}{num}"

def registrar_orden(productos: list, encargada: str) -> str:
    """
    Registra la orden en el Sheet con etiquetas descriptivas.
    """
    service = _get_service()
    _ensure_headers(service)
    
    id_orden = generar_id_orden()
    fecha = datetime.now().strftime("%d/%m/%Y")

    rows = []
    for i, p in enumerate(productos):
        rows.append([
            f"Folio: {id_orden}"   if i == 0 else "",
            f"Fecha: {fecha}"      if i == 0 else "",
            f"Encargada: {encargada}" if i == 0 else "",
            p.get("producto", ""),
            p.get("cantidad", ""),
            p.get("marca", ""),
        ])

    service.spreadsheets().values().append(
        spreadsheetId=OC_SPREADSHEET_ID,
        range=f"{OC_SHEET}!A1",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": rows}
    ).execute()
    
    return id_orden

def texto_resumen_oc(productos: list, encargada: str) -> str:
    """Genera resumen legible para Telegram."""
    lines = [
        f"📋 *Resumen de la orden*",
        f"👤 Encargada: {encargada}",
        f"📦 Productos ({len(productos)}):\n"
    ]
    for i, p in enumerate(productos, 1):
        linea = f"{i}. *{p['producto']}* — {p['cantidad']}"
        if p.get("marca"):
            linea += f" ({p['marca']})"
        lines.append(linea)
    return "\n".join(lines)