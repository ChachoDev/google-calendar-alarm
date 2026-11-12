from __future__ import annotations

import base64
import json
import os
import threading
import time
import webbrowser
import wsgiref.simple_server
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

try:
    # Clases internas que usa ``InstalledAppFlow.run_local_server``: el
    # servidor reserva el puerto en exclusiva (Windows) y también ``::1``, y el
    # manejador no escribe en la consola. Si cambian, se usa wsgiref tal cual.
    from google_auth_oauthlib.flow import (  # type: ignore[attr-defined]
        _ExclusiveWSGIServer as _LocalServer,
    )
    from google_auth_oauthlib.flow import (  # type: ignore[attr-defined]
        _RedirectWSGIApp as _RedirectApp,
    )
    from google_auth_oauthlib.flow import (  # type: ignore[attr-defined]
        _WSGIRequestHandler as _RequestHandler,
    )
except ImportError:  # pragma: no cover - depende de la versión de la librería
    _LocalServer = wsgiref.simple_server.WSGIServer

    class _RequestHandler(wsgiref.simple_server.WSGIRequestHandler):
        def log_message(self, *args) -> None:
            pass

    class _RedirectApp:
        def __init__(self, success_message: str) -> None:
            self.last_request_uri: str | None = None
            self._success_message = success_message

        def __call__(self, environ, start_response):
            import wsgiref.util

            start_response("200 OK", [("Content-type", "text/plain; charset=utf-8")])
            self.last_request_uri = wsgiref.util.request_uri(environ)
            return [self._success_message.encode("utf-8")]


from calendar_alarm.oauth_client import client_config

# calendar.readonly: leer eventos. openid/userinfo.email: mostrar la cuenta.
CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"
SCOPES = [
    CALENDAR_SCOPE,
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]

# Google normaliza y reordena los scopes en la respuesta (p. ej. «email» pasa a
# «userinfo.email», y el orden puede cambiar). oauthlib lo interpreta como un
# cambio de permisos y aborta con «Scope has changed». Con esta variable acepta
# la respuesta y comprobamos después que el calendario sí esté autorizado.
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

# Tiempo máximo esperando a que el usuario autorice en el navegador. Sin límite,
# cerrar la pestaña dejaría el servidor local (y el hilo) esperando para siempre.
# El usuario también puede cancelar antes desde la interfaz.
SIGN_IN_TIMEOUT_SECONDS = 300
# Cada cuánto se comprueba si el usuario ha cancelado mientras se espera.
_POLL_SECONDS = 0.25

_SUCCESS_MESSAGE = "Calendar Alarm ya tiene acceso a tu calendario. Puedes cerrar esta ventana."


class GoogleAuthError(RuntimeError):
    """Error controlado en el flujo de autenticación con Google."""


class SignInCancelled(GoogleAuthError):
    """El usuario canceló la autorización desde la aplicación."""


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
            # El token da acceso al calendario: solo legible por el usuario
            # (en Windows chmod solo afecta al atributo de solo lectura).
            if os.name != "nt":
                self._token_path.chmod(0o600)
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
        """Credenciales válidas (refrescando el token si caducó). Llama a Google.

        Devuelve None si no hay sesión. Lanza ``GoogleAuthError`` si la sesión
        existe pero no se puede renovar, para que el usuario vea el motivo en
        lugar de un calendario aparentemente vacío.
        """
        with self._lock:
            creds = self._creds
        if creds is None:
            return None
        if creds.expired and creds.refresh_token:
            try:
                with self._lock:
                    creds.refresh(Request())
                    self._save(creds)
            except RefreshError as exc:
                raise GoogleAuthError(
                    "La sesión de Google ha caducado o se ha revocado. "
                    "Pulsa «Cambiar de cuenta» para volver a conectar."
                ) from exc
            except Exception as exc:
                raise GoogleAuthError(f"No se pudo renovar la sesión de Google: {exc}") from exc
        return creds if creds.valid else None

    # ------------------------------------------------------------- acciones
    def sign_in(
        self,
        *,
        select_account: bool = True,
        cancel: threading.Event | None = None,
    ) -> str | None:
        """Abre el navegador para autenticarse. Devuelve el correo conectado.

        `select_account=True` fuerza el selector de cuentas de Google, lo que
        permite autenticarse con otra cuenta distinta de la actual. Las
        credenciales del cliente OAuth van incluidas en la aplicación
        (ver `calendar_alarm.oauth_client`).

        Si se activa `cancel`, la espera termina en menos de un segundo con
        `SignInCancelled`.
        """
        config = client_config()
        if config is None:
            raise GoogleAuthError(
                "Esta compilación no tiene configurada la aplicación de Google. "
                "Consulta «Configurar Google» en la documentación."
            )
        try:
            flow = InstalledAppFlow.from_client_config(config, SCOPES)
            # «consent» obliga a mostrar la pantalla de permisos (así el
            # usuario puede marcar Google Calendar aunque ya hubiera autorizado
            # la cuenta antes); «select_account» permite elegir otra cuenta.
            prompt = "consent select_account" if select_account else None
            creds = _run_local_flow(flow, prompt=prompt, cancel=cancel or threading.Event())
        except GoogleAuthError:
            raise
        except Exception as exc:
            raise GoogleAuthError(f"Error al autenticar con Google: {exc}") from exc

        granted = set(creds.scopes or [])
        if granted and CALENDAR_SCOPE not in granted:
            raise GoogleAuthError(
                "No se ha concedido acceso al calendario. Vuelve a pulsar "
                "«Conectar con Google» y deja marcada la casilla de "
                "Google Calendar."
            )

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


def _run_local_flow(
    flow: InstalledAppFlow, *, prompt: str | None, cancel: threading.Event
) -> Credentials:
    """Equivalente a ``flow.run_local_server`` pero cancelable.

    La librería bloquea en una única espera de hasta ``timeout_seconds`` sin
    forma de interrumpirla. Aquí se atiende el servidor local en intervalos
    cortos para poder salir en cuanto el usuario cancela.
    """
    redirect = _RedirectApp(_SUCCESS_MESSAGE)
    server = wsgiref.simple_server.make_server(
        "localhost", 0, redirect, server_class=_LocalServer, handler_class=_RequestHandler
    )
    try:
        server.timeout = _POLL_SECONDS
        flow.redirect_uri = f"http://localhost:{server.server_port}/"
        extra = {"prompt": prompt} if prompt else {}
        auth_url, _ = flow.authorization_url(**extra)
        webbrowser.open(auth_url, new=1, autoraise=True)

        deadline = time.monotonic() + SIGN_IN_TIMEOUT_SECONDS
        while redirect.last_request_uri is None:
            if cancel.is_set():
                raise SignInCancelled("Conexión con Google cancelada.")
            if time.monotonic() > deadline:
                raise GoogleAuthError(
                    "No se completó la autorización en el navegador a tiempo. "
                    "Vuelve a pulsar «Conectar con Google»."
                )
            server.handle_request()
        response_uri = redirect.last_request_uri
    finally:
        server.server_close()

    if cancel.is_set():
        raise SignInCancelled("Conexión con Google cancelada.")

    error = parse_qs(urlsplit(response_uri).query).get("error", [""])[0]
    if error == "access_denied":
        raise GoogleAuthError("Has denegado el acceso en Google. No se ha conectado la cuenta.")
    if error:
        raise GoogleAuthError(f"Google rechazó la autorización: {error}")

    # oauthlib exige https aunque la redirección local sea http (igual que la
    # propia librería en run_local_server).
    flow.fetch_token(authorization_response=response_uri.replace("http", "https", 1))
    return flow.credentials  # type: ignore[return-value]
