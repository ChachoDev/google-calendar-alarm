"""Credenciales del cliente OAuth de Google incluidas en la aplicación.

La aplicación no pide al usuario ningún ``client_secret.json``: el botón
«Conectar con Google» abre directamente el navegador. Para ello necesita un
cliente OAuth de tipo *Aplicación de escritorio* registrado en Google Cloud.

Fuentes, por orden de prioridad:

1. Constantes ``CLIENT_ID`` / ``CLIENT_SECRET`` de este módulo (recomendado:
   quedan dentro del binario, sin archivos externos).
2. Variables de entorno (útil en desarrollo):
   - ``CALENDAR_ALARM_GOOGLE_CLIENT_FILE``: ruta a un JSON de credenciales.
   - ``CALENDAR_ALARM_GOOGLE_CLIENT_ID`` + ``CALENDAR_ALARM_GOOGLE_CLIENT_SECRET``.
3. Recurso empaquetado ``calendar_alarm/assets/google_client.json`` (opcional).

Google considera que el secreto de un cliente de aplicación instalada **no es
confidencial** (viaja en el binario); aun así, el archivo debe tratarse como
configuración del proyecto.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from calendar_alarm.config import asset_path

CLIENT_FILE = "assets/google_client.json"

AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
TOKEN_URI = "https://oauth2.googleapis.com/token"

# --------------------------------------------------------------------------
# Credenciales de la aplicación (se rellenan UNA vez).
#
# No hace falta ningún archivo: pega aquí el client_id y el client_secret de
# tu cliente OAuth de tipo «Aplicación de escritorio» (Google Cloud Console →
# Credenciales). El usuario final no rellena nada: solo pulsa «Conectar con
# Google» y el navegador se abre.
#
# Google considera que el secreto de un cliente de aplicación instalada no es
# confidencial (viaja dentro del binario); aun así, no publiques credenciales
# de tipo «Aplicación web».
# --------------------------------------------------------------------------
CLIENT_ID = ""
CLIENT_SECRET = ""

ENV_FILE = "CALENDAR_ALARM_GOOGLE_CLIENT_FILE"
ENV_ID = "CALENDAR_ALARM_GOOGLE_CLIENT_ID"
ENV_SECRET = "CALENDAR_ALARM_GOOGLE_CLIENT_SECRET"


def _from_constants() -> dict[str, Any] | None:
    if CLIENT_ID and CLIENT_SECRET:
        return {
            "installed": {
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "auth_uri": AUTH_URI,
                "token_uri": TOKEN_URI,
            }
        }
    return None


def _from_env() -> dict[str, Any] | None:
    file_path = os.environ.get(ENV_FILE, "").strip()
    if file_path:
        config = _read_client_file(Path(file_path).expanduser())
        if config is not None:
            return config

    client_id = os.environ.get(ENV_ID, "").strip()
    client_secret = os.environ.get(ENV_SECRET, "").strip()
    if client_id and client_secret:
        return {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": AUTH_URI,
                "token_uri": TOKEN_URI,
            }
        }
    return None


def _read_client_file(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    section = data.get("installed") or data.get("web")
    if not isinstance(section, dict) or not section.get("client_id"):
        return None
    return {"installed": section}


def client_config() -> dict[str, Any] | None:
    """Configuración OAuth lista para ``InstalledAppFlow``, o None si falta."""
    return _from_constants() or _from_env() or _read_client_file(asset_path(CLIENT_FILE))


def is_configured() -> bool:
    return client_config() is not None
