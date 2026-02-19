import os
import logging
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from google_drive import _get_creds

logger = logging.getLogger(__name__)

INV_SPREADSHEET_ID = os.environ.get("INV_SPREADSHEET_ID")
SHEETS_MAP = {"cocina": "inventario cocina", "cafeteria": "front-v.actual"}

def _get_service():
    return build(
        "sheets", "v4", credentials=_get_creds(),
        discoveryServiceUrl="https://sheets.googleapis.com/$discovery/rest?version=v4"
    )

def _get_column_mapping(sheet_name):
    service = _get_service()
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=INV_SPREADSHEET_ID, range=f"'{sheet_name}'!A1:Z1"
        ).execute()
        headers = result.get('values', [[]])[0]
        return {h.strip().lower(): chr(65 + i) for i, h in enumerate(headers)}
    except: return {}

def buscar_articulo(seccion: str, nombre: str):
    service = _get_service()
    sheet_name = SHEETS_MAP.get(seccion)
    mapping = _get_column_mapping(sheet_name)
    col_n = mapping.get("artículo", mapping.get("articulo", "A"))
    col_c = mapping.get("cantidad actual", "D")
    try:
        res = service.spreadsheets().values().get(spreadsheetId=INV_SPREADSHEET_ID, range=f"'{sheet_name}'!A:Z").execute()
        values = res.get('values', [])
        idx_n, idx_c = ord(col_n)-65, ord(col_c)-65
        for i, row in enumerate(values):
            if len(row) > idx_n and nombre.lower() in row[idx_n].lower():
                return {"fila": i+1, "nombre": row[idx_n], "cantidad_actual": row[idx_c] if len(row)>idx_c else "0", "seccion": seccion}
        return None
    except: return None

def obtener_total_paginado(filtro="todo"):
    service = _get_service()
    todos = []
    ahora = datetime.now()
    for seccion, sheet_name in SHEETS_MAP.items():
        mapping = _get_column_mapping(sheet_name)
        res = service.spreadsheets().values().get(spreadsheetId=INV_SPREADSHEET_ID, range=f"'{sheet_name}'!A:Z").execute()
        values = res.get('values', [])
        if not values: continue
        headers = [h.lower() for h in values[0]]
        idx_n, idx_c, idx_m = ord(mapping.get("artículo", "A"))-65, ord(mapping.get("cantidad actual", "D"))-65, ord(mapping.get("mínimo", "H"))-65
        idx_f = next((i for i, h in enumerate(headers) if any(x in h for x in ["actualiza", "fecha"])), -1)
        data = reversed(values[1:]) if filtro == "todo" else values[1:]
        for row in data:
            if len(row) <= idx_n: continue
            if filtro == "minimos":
                try:
                    c = float(row[idx_c].replace(',','.'))
                    m = float(row[idx_m].replace(',','.'))
                    if c > m: continue
                except: continue
            elif filtro == "viejos" and idx_f != -1:
                try:
                    f_upd = datetime.strptime(row[idx_f].split(" ")[0], "%d/%m/%Y")
                    if ahora - f_upd < timedelta(days=5): continue
                except: continue
            todos.append({"nombre": row[idx_n], "cantidad": row[idx_c] if len(row)>idx_c else "0", "seccion": seccion})
    return todos

def actualizar_cantidad(seccion, fila, nueva_cant):
    service = _get_service()
    sheet_name = SHEETS_MAP.get(seccion)
    col = _get_column_mapping(sheet_name).get("cantidad actual", "D")
    service.spreadsheets().values().update(
        spreadsheetId=INV_SPREADSHEET_ID, range=f"'{sheet_name}'!{col}{fila}",
        valueInputOption="USER_ENTERED", body={"values": [[nueva_cant]]}).execute()

def agregar_nuevo_articulo(seccion, d):
    service = _get_service()
    sheet_name = SHEETS_MAP.get(seccion)
    row = [d.get('articulo',''), d.get('marca',''), d.get('contenido',''), d.get('cantidad','0'), d.get('unidad',''), d.get('categoria',''), d.get('notas',''), d.get('minimo','0')]
    service.spreadsheets().values().append(spreadsheetId=INV_SPREADSHEET_ID, range=f"'{sheet_name}'!A1", valueInputOption="USER_ENTERED", insertDataOption="INSERT_ROWS", body={"values": [row]}).execute()

def obtener_articulos_bajos(seccion):
    service = _get_service()
    sheet_name = SHEETS_MAP.get(seccion)
    mapping = _get_column_mapping(sheet_name)
    idx_n, idx_c, idx_m = ord(mapping.get("artículo", "A"))-65, ord(mapping.get("cantidad actual", "D"))-65, ord(mapping.get("mínimo", "H"))-65
    try:
        res = service.spreadsheets().values().get(spreadsheetId=INV_SPREADSHEET_ID, range=f"'{sheet_name}'!A:Z").execute()
        bajos = []
        for row in res.get('values', [])[1:]:
            if len(row) > max(idx_n, idx_c, idx_m):
                try:
                    if float(row[idx_c].replace(',','.')) <= float(row[idx_m].replace(',','.')):
                        bajos.append(f"• *{row[idx_n]}*: {row[idx_c]} (Min: {row[idx_m]})")
                except: continue
        return bajos
    except: return []