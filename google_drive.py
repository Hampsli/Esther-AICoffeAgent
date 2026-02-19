import os
import io
import pickle
from datetime import datetime
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets"
]

CREDENTIALS_FILE = os.environ.get("GOOGLE_CREDENTIALS_PATH", "/app/credentials.json")
TOKEN_FILE = os.environ.get("GOOGLE_TOKEN_PATH", "/app/token.pickle")
DRIVE_FOLDER_ID = os.environ.get("DRIVE_FOLDER_ID", "")  # Carpeta raíz del bot


def _get_creds():
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=8080, open_browser=False)
        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)
    return creds


def _get_service():
    return build("drive", "v3", credentials=_get_creds())


def list_folders() -> list:
    """Lista todas las subcarpetas dentro de la carpeta raíz del bot."""
    service = _get_service()
    query = "mimeType='application/vnd.google-apps.folder' and trashed=false"
    if DRIVE_FOLDER_ID:
        query += f" and '{DRIVE_FOLDER_ID}' in parents"

    results = service.files().list(
        q=query,
        fields="files(id, name)",
        orderBy="name"
    ).execute()
    return results.get("files", [])


def create_folder(name: str) -> str:
    """Crea una nueva carpeta en Drive y retorna su ID."""
    service = _get_service()
    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder"
    }
    if DRIVE_FOLDER_ID:
        metadata["parents"] = [DRIVE_FOLDER_ID]

    folder = service.files().create(body=metadata, fields="id").execute()
    return folder["id"]


def get_folder_id_by_name(name: str) -> str | None:
    """Busca una carpeta por nombre y retorna su ID."""
    folders = list_folders()
    for f in folders:
        if f["name"].lower() == name.lower():
            return f["id"]
    return None


def upload_file_to_drive(file_bytes: bytearray, file_name: str, mime_type: str, folder_id: str = None) -> str:
    """Sube un archivo a Drive. Si folder_id es None usa la carpeta raíz."""
    service = _get_service()

    parent = folder_id or DRIVE_FOLDER_ID
    file_metadata = {"name": file_name}
    if parent:
        file_metadata["parents"] = [parent]

    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=True)
    uploaded = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id"
    ).execute()

    file_id = uploaded["id"]
    service.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"}
    ).execute()

    return f"https://drive.google.com/file/d/{file_id}/view"


def list_files_in_folder(folder_id: str = None) -> list:
    """Lista archivos dentro de una carpeta específica o la carpeta raíz."""
    service = _get_service()
    parent = folder_id or DRIVE_FOLDER_ID
    query = f"'{parent}' in parents and trashed=false and mimeType!='application/vnd.google-apps.folder'"
    results = service.files().list(
        q=query,
        fields="files(id, name, mimeType, createdTime)",
        orderBy="createdTime desc"
    ).execute()
    return results.get("files", [])