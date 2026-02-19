"""
Ejecuta este script UNA SOLA VEZ en tu PC (fuera de Docker)
para autorizar el acceso a tu cuenta de Google.

Genera el archivo token.pickle que el bot usará después.

Uso:
    pip install google-auth-oauthlib google-api-python-client
    python setup_auth.py
"""

import pickle
import os
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets"
]

def main():
    credentials_path = input("Ruta a tu credentials.json [./credentials.json]: ").strip()
    if not credentials_path:
        credentials_path = "./credentials.json"

    if not os.path.exists(credentials_path):
        print(f"❌ No encontré el archivo: {credentials_path}")
        return

    print("\n🌐 Se abrirá tu navegador para autorizar el acceso...")
    print("   Inicia sesión con tu Gmail y acepta los permisos.\n")

    flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
    creds = flow.run_local_server(port=8080)

    token_path = "./token.pickle"
    with open(token_path, "wb") as f:
        pickle.dump(creds, f)

    print(f"\n✅ ¡Listo! Token guardado en: {token_path}")
    print("   Copia token.pickle a la carpeta del proyecto antes de correr Docker.")


if __name__ == "__main__":
    main()
