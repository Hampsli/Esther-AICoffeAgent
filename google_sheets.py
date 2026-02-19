import os
from datetime import datetime
from googleapiclient.discovery import build
from google_drive import _get_creds

SPREADSHEET_ID = os.environ["SPREADSHEET_ID"]
HEADERS = ["Fecha", "Hora", "Usuario", "Tipo", "Nombre / URL", "Tipo MIME", "Link", "Nota"]


def _get_service():
    return build("sheets", "v4", credentials=_get_creds())


def list_sheets() -> list[str]:
    """Retorna los nombres de todas las páginas del spreadsheet."""
    service = _get_service()
    meta = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
    return [s["properties"]["title"] for s in meta["sheets"]]


def create_sheet(name: str):
    """Crea una nueva página en el spreadsheet."""
    service = _get_service()
    service.spreadsheets().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={"requests": [{"addSheet": {"properties": {"title": name}}}]}
    ).execute()
    # Agregar encabezados a la nueva página
    service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{name}!A1",
        valueInputOption="RAW",
        body={"values": [HEADERS]}
    ).execute()


def _ensure_headers(service, sheet_name: str):
    """Crea encabezados si la página está vacía."""
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{sheet_name}!A1:H1"
    ).execute()
    if not result.get("values"):
        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{sheet_name}!A1",
            valueInputOption="RAW",
            body={"values": [HEADERS]}
        ).execute()


def log_to_sheet(tipo: str, nombre: str, link: str, mime: str,
                 nota: str, usuario: str, sheet_name: str = "Registro"):
    """Agrega una fila en la página especificada del spreadsheet."""
    service = _get_service()

    # Si la página no existe, la creamos
    existing = list_sheets()
    if sheet_name not in existing:
        create_sheet(sheet_name)
    else:
        _ensure_headers(service, sheet_name)

    now = datetime.now()
    row = [
        now.strftime("%d/%m/%Y"),
        now.strftime("%H:%M:%S"),
        usuario,
        tipo,
        nombre,
        mime,
        link,
        nota
    ]

    service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{sheet_name}!A1",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]}
    ).execute()