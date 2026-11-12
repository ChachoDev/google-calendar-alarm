from __future__ import annotations

import base64
import json
import threading
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# calendar.readonly: leer eventos. openid/email: mostrar la cuenta conectada.
SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "openid",
    "email",
]


class GoogleAuthError(RuntimeError):
    """Error controlado en el flujo de autenticación con Google."""


class GoogleAuth:
    """Gestión de la sesión de Google: conectar, cambiar de cuenta y desconectar.

    El token se guarda en el directorio de configuración del usuario.
    Todas las operaciones están protegidas con un lock porque el hilo de
    fondo (consultas) y la interfaz gráfica acceden a la vez.
    """

    def __init__(self, config_dir: Path) -> None:
        self._token_path = config_dir / "token.json"
        self._lock = threading.Lock()
        self._creds: Credentials | None = self._load()

    # ------------------------------------------------------------- token I/O
    def _load(self) -> Credentials | None:
        if not self._token_path.exists():
            return None
        try:
            return Credentials.from_authorized_user_file(str(self._token_path), SCOPES)
        except Exception:
            return None

    def _save(self, creds: Credentials) -> None:
        try:
            self._token_path.write_text(creds.to_json(), encoding="utf-8")
        except OSError:
            pass

    # -------------------------------------------------------------- estado
    @property
    def is_authenticated(self) -> bool:
        with self._lock:
            creds = self._creds
        if creds is None:
            return False
        return bool(creds.valid or creds.refresh_token)

    @property
    def account_email(self) -> str | None:
        with self._lock:
            creds = self._creds
        if creds is None:
            return None
        return _email_from_credentials(creds)

    def get_credentials(self) -> Credentials | None:
        """Credenciales válidas (refrescando el token si caducó). Llama a Google."""
        with self._lock:
            creds = self._creds
        if creds is None:
            return None
        if creds.expired and creds.refresh_token:
            try:
                with self._lock:
                    creds.refresh(Request())
                    self._save(creds)
            except Exception:
                return None
        return creds if creds.valid else None

    # ------------------------------------------------------------- acciones
    def sign_in(self, client_secret_path: str, *, select_account: bool = True) -> str | None:
        """Abre el navegador para autenticarse. Devuelve el correo conectado.

        `select_account=True` fuerza el selector de cuentas de Google, lo que
        permite autenticarse con otra cuenta distinta de la actual.
        """
        path = Path(client_secret_path).expanduser() if client_secret_path else None
        if path is None or not path.is_file():
            raise GoogleAuthError(
                "No se encontró el archivo client_secret.json de Google Cloud. "
                "Selecciona primero ese archivo con el botón «Examinar…»."
            )
        try:
            flow = InstalledAppFlow.from_client_secrets_file(str(path), SCOPES)
            kwargs: dict[str, object] = {"port": 0, "open_browser": True}
            if select_account:
                kwargs["prompt"] = "select_account"
            creds = flow.run_local_server(**kwargs)  # type: ignore[arg-type]
        except GoogleAuthError:
            raise
        except Exception as exc:
            raise GoogleAuthError(f"Error al autenticar con Google: {exc}") from exc

        with self._lock:
            self._creds = creds
            self._save(creds)
        return self.account_email

    def sign_out(self) -> None:
        """Elimina el token local: la aplicación queda desconectada."""
        with self._lock:
            self._creds = None
            try:
                self._token_path.unlink(missing_ok=True)
            except OSError:
                pass


def _email_from_credentials(creds: Credentials) -> str | None:
    """Extrae el correo del id_token emitido por el flujo OAuth (claim 'email')."""
    token = getattr(creds, "id_token", None)
    if not token:
        return None
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload))
        return data.get("email")
    except Exception:
        return None
