from __future__ import annotations

import base64
import json
import os
import stat
import threading
import time
import urllib.request
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlsplit

import pytest
from google.auth.exceptions import RefreshError

from calendar_alarm import auth as auth_module
from calendar_alarm.auth import (
    CALENDAR_SCOPE,
    GoogleAuth,
    GoogleAuthError,
    SignInCancelled,
    _email_from_credentials,
)


def id_token(payload: dict) -> str:
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"header.{body}.firma"


class FakeCreds:
    def __init__(self, *, valid=True, expired=False, refresh_token="r", scopes=None, email=None):
        self.valid = valid
        self.expired = expired
        self.refresh_token = refresh_token
        self.scopes = scopes if scopes is not None else [CALENDAR_SCOPE]
        self.id_token = id_token({"email": email}) if email else None
        self.refresh_calls = 0
        self.refresh_error: Exception | None = None

    def refresh(self, _request):
        self.refresh_calls += 1
        if self.refresh_error:
            raise self.refresh_error
        self.valid, self.expired = True, False

    def to_json(self):
        return json.dumps({"token": "t"})


@pytest.fixture
def auth(tmp_path):
    return GoogleAuth(tmp_path)


# ------------------------------------------------------------------ token
def test_email_desde_id_token():
    creds = FakeCreds(email="ana@example.com")
    assert _email_from_credentials(creds) == "ana@example.com"  # type: ignore[arg-type]


def test_email_sin_token_o_token_roto():
    assert _email_from_credentials(FakeCreds()) is None  # type: ignore[arg-type]
    creds = FakeCreds()
    creds.id_token = "sin-puntos"
    assert _email_from_credentials(creds) is None  # type: ignore[arg-type]
    creds.id_token = "a.@@@.c"
    assert _email_from_credentials(creds) is None  # type: ignore[arg-type]


def test_email_con_padding_necesario():
    # Longitudes de payload que exigen 1, 2 y 3 caracteres de relleno.
    for email in ("a@b.c", "ab@b.c", "abc@b.c", "abcd@b.c"):
        assert _email_from_credentials(FakeCreds(email=email)) == email  # type: ignore[arg-type]


def test_sin_token_guardado(auth):
    assert auth.is_authenticated is False
    assert auth.account_email is None
    assert auth.get_credentials() is None


def test_token_corrupto_se_ignora(tmp_path):
    (tmp_path / "token.json").write_text("basura", encoding="utf-8")
    assert GoogleAuth(tmp_path).is_authenticated is False


def test_token_guardado_se_carga(tmp_path):
    (tmp_path / "token.json").write_text(
        json.dumps(
            {
                "token": "t",
                "refresh_token": "r",
                "client_id": "c",
                "client_secret": "s",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        ),
        encoding="utf-8",
    )
    assert GoogleAuth(tmp_path).is_authenticated is True


def test_guardar_token_es_privado_en_posix(auth, tmp_path):
    auth._save(FakeCreds())
    path = tmp_path / "token.json"
    assert json.loads(path.read_text(encoding="utf-8")) == {"token": "t"}
    if os.name != "nt":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_guardar_token_tolera_errores(auth, monkeypatch):
    monkeypatch.setattr(auth, "_token_path", auth._token_path.parent / "no" / "existe" / "t.json")
    auth._save(FakeCreds())  # no lanza


@pytest.mark.parametrize(
    ("valid", "refresh_token", "expected"),
    [(True, None, True), (False, "r", True), (False, None, False)],
)
def test_is_authenticated(auth, valid, refresh_token, expected):
    auth._creds = FakeCreds(valid=valid, refresh_token=refresh_token)
    assert auth.is_authenticated is expected


def test_account_email(auth):
    auth._creds = FakeCreds(email="eva@example.com")
    assert auth.account_email == "eva@example.com"


# ------------------------------------------------------------ renovación
def test_get_credentials_validas_no_refresca(auth):
    creds = FakeCreds()
    auth._creds = creds
    assert auth.get_credentials() is creds
    assert creds.refresh_calls == 0


def test_get_credentials_caducadas_se_refrescan_y_guardan(auth, tmp_path):
    creds = FakeCreds(valid=False, expired=True)
    auth._creds = creds
    assert auth.get_credentials() is creds
    assert creds.refresh_calls == 1
    assert (tmp_path / "token.json").exists()


def test_get_credentials_caducadas_sin_refresh_token(auth):
    auth._creds = FakeCreds(valid=False, expired=True, refresh_token=None)
    assert auth.get_credentials() is None


def test_get_credentials_invalidas_sin_caducar(auth):
    auth._creds = FakeCreds(valid=False, expired=False)
    assert auth.get_credentials() is None


def test_refresh_revocado_explica_que_hay_que_reconectar(auth):
    creds = FakeCreds(valid=False, expired=True)
    creds.refresh_error = RefreshError("invalid_grant")
    auth._creds = creds
    with pytest.raises(GoogleAuthError, match="caducado o se ha revocado"):
        auth.get_credentials()


def test_refresh_con_error_de_red(auth):
    creds = FakeCreds(valid=False, expired=True)
    creds.refresh_error = OSError("sin red")
    auth._creds = creds
    with pytest.raises(GoogleAuthError, match="No se pudo renovar la sesión de Google: sin red"):
        auth.get_credentials()


def test_sign_out_borra_token(auth, tmp_path):
    auth._creds = FakeCreds()
    auth._save(FakeCreds())
    auth.sign_out()
    assert auth.is_authenticated is False
    assert not (tmp_path / "token.json").exists()
    auth.sign_out()  # idempotente


# ------------------------------------------------------------------ sign_in
def test_sign_in_sin_cliente_configurado(auth, no_bundled_client):
    with pytest.raises(GoogleAuthError, match="no tiene configurada"):
        auth.sign_in()


def fake_flow_runner(monkeypatch, creds=None, error=None):
    calls = {}

    def runner(flow, *, prompt, cancel):
        calls.update(flow=flow, prompt=prompt, cancel=cancel)
        if error is not None:
            raise error
        return creds

    monkeypatch.setattr(auth_module, "_run_local_flow", runner)
    return calls


def test_sign_in_correcto_guarda_y_devuelve_email(auth, dummy_client, monkeypatch, tmp_path):
    calls = fake_flow_runner(monkeypatch, creds=FakeCreds(email="ok@example.com"))
    assert auth.sign_in() == "ok@example.com"
    assert calls["prompt"] == "consent select_account"
    assert isinstance(calls["cancel"], threading.Event)
    assert auth.is_authenticated
    assert (tmp_path / "token.json").exists()


def test_sign_in_sin_selector_de_cuenta(auth, dummy_client, monkeypatch):
    calls = fake_flow_runner(monkeypatch, creds=FakeCreds())
    auth.sign_in(select_account=False)
    assert calls["prompt"] is None


def test_sign_in_pasa_el_evento_de_cancelacion(auth, dummy_client, monkeypatch):
    calls = fake_flow_runner(monkeypatch, creds=FakeCreds())
    cancel = threading.Event()
    auth.sign_in(cancel=cancel)
    assert calls["cancel"] is cancel


def test_sign_in_sin_permiso_de_calendario(auth, dummy_client, monkeypatch):
    fake_flow_runner(monkeypatch, creds=FakeCreds(scopes=["openid"]))
    with pytest.raises(GoogleAuthError, match="No se ha concedido acceso al calendario"):
        auth.sign_in()
    assert auth.is_authenticated is False


def test_sign_in_sin_lista_de_scopes_se_acepta(auth, dummy_client, monkeypatch):
    fake_flow_runner(monkeypatch, creds=FakeCreds(scopes=[]))
    auth.sign_in()
    assert auth.is_authenticated


def test_sign_in_cancelado_se_propaga(auth, dummy_client, monkeypatch):
    fake_flow_runner(monkeypatch, error=SignInCancelled("cancelado"))
    with pytest.raises(SignInCancelled):
        auth.sign_in()


def test_sign_in_error_inesperado_se_envuelve(auth, dummy_client, monkeypatch):
    fake_flow_runner(monkeypatch, error=ValueError("boom"))
    with pytest.raises(GoogleAuthError, match="Error al autenticar con Google: boom"):
        auth.sign_in()


# -------------------------------------------- flujo local real (sin Google)
class FakeFlow:
    """Sustituye a InstalledAppFlow: genera la URL y registra el canje del código."""

    def __init__(self):
        self.redirect_uri = None
        self.fetched = None
        self.credentials = FakeCreds(email="flow@example.com")

    def authorization_url(self, **kwargs):
        self.auth_kwargs = kwargs
        return f"https://accounts.example/auth?redirect_uri={self.redirect_uri}", "state"

    def fetch_token(self, authorization_response):
        self.fetched = authorization_response


@pytest.fixture
def browser(monkeypatch):
    opened: list[str] = []
    monkeypatch.setattr(auth_module.webbrowser, "open", lambda url, **_k: opened.append(url))
    return opened


def start_flow(flow, cancel=None, prompt="consent"):
    result: dict = {}
    cancel = cancel or threading.Event()

    def target():
        try:
            result["creds"] = auth_module._run_local_flow(flow, prompt=prompt, cancel=cancel)
        except Exception as exc:
            result["error"] = exc

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    return thread, result, cancel


def wait_for_browser(opened, timeout=3.0):
    deadline = time.monotonic() + timeout
    while not opened and time.monotonic() < deadline:
        time.sleep(0.02)
    assert opened, "no se abrió el navegador"
    return parse_qs(urlsplit(opened[0]).query)["redirect_uri"][0]


def test_flujo_local_canjea_el_codigo(browser):
    flow = FakeFlow()
    thread, result, _ = start_flow(flow)
    redirect = wait_for_browser(browser)
    assert redirect.startswith("http://localhost:") and redirect.endswith("/")
    assert flow.auth_kwargs == {"prompt": "consent"}

    body = urllib.request.urlopen(redirect + "?code=abc&state=state", timeout=5).read()
    thread.join(5)
    assert "Calendar Alarm" in body.decode("utf-8")
    assert result.get("creds") is flow.credentials
    assert flow.fetched.startswith("https://localhost:")
    assert "code=abc" in flow.fetched


def test_flujo_local_sin_prompt(browser):
    flow = FakeFlow()
    thread, _, cancel = start_flow(flow, prompt=None)
    wait_for_browser(browser)
    assert flow.auth_kwargs == {}
    cancel.set()
    thread.join(3)


def test_flujo_local_cancelado_termina_rapido(browser):
    thread, result, cancel = start_flow(FakeFlow())
    wait_for_browser(browser)
    started = time.monotonic()
    cancel.set()
    thread.join(3)
    assert not thread.is_alive()
    assert time.monotonic() - started < 1.0
    assert isinstance(result.get("error"), SignInCancelled)


def test_flujo_local_cancelado_justo_al_recibir_respuesta(browser):
    flow = FakeFlow()
    cancel = threading.Event()
    original = flow.fetch_token
    flow.fetch_token = MagicMock(side_effect=original)
    thread, result, _ = start_flow(flow, cancel=cancel)
    redirect = wait_for_browser(browser)
    cancel.set()
    try:
        urllib.request.urlopen(redirect + "?code=abc", timeout=2).read()
    except OSError:
        pass  # el servidor puede haberse cerrado ya
    thread.join(3)
    assert isinstance(result.get("error"), SignInCancelled)
    flow.fetch_token.assert_not_called()


def test_flujo_local_acceso_denegado(browser):
    thread, result, _ = start_flow(FakeFlow())
    redirect = wait_for_browser(browser)
    urllib.request.urlopen(redirect + "?error=access_denied", timeout=5).read()
    thread.join(5)
    error = result.get("error")
    assert isinstance(error, GoogleAuthError) and not isinstance(error, SignInCancelled)
    assert "Has denegado el acceso" in str(error)


def test_flujo_local_otro_error_de_google(browser):
    thread, result, _ = start_flow(FakeFlow())
    redirect = wait_for_browser(browser)
    urllib.request.urlopen(redirect + "?error=invalid_scope", timeout=5).read()
    thread.join(5)
    assert str(result.get("error")) == "Google rechazó la autorización: invalid_scope"


def test_flujo_local_agota_el_tiempo(browser, monkeypatch):
    monkeypatch.setattr(auth_module, "SIGN_IN_TIMEOUT_SECONDS", 0.3)
    thread, result, _ = start_flow(FakeFlow())
    thread.join(5)
    assert not thread.is_alive()
    assert "a tiempo" in str(result.get("error"))
    assert not isinstance(result.get("error"), SignInCancelled)


def test_flujo_local_libera_el_puerto(browser):
    thread, _, cancel = start_flow(FakeFlow())
    redirect = wait_for_browser(browser)
    cancel.set()
    thread.join(3)
    with pytest.raises(OSError):
        urllib.request.urlopen(redirect, timeout=1)


# ------------------------------------------- refuerzos (tests de mutación)
def test_token_se_guarda_exactamente_como_token_json(auth, tmp_path):
    auth._save(FakeCreds())
    assert [p.name for p in tmp_path.iterdir()] == ["token.json"]


def test_token_cargado_conserva_los_permisos_pedidos(tmp_path):
    (tmp_path / "token.json").write_text(
        json.dumps(
            {
                "token": "t",
                "refresh_token": "r",
                "client_id": "c",
                "client_secret": "s",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        ),
        encoding="utf-8",
    )
    assert GoogleAuth(tmp_path)._creds.scopes == auth_module.SCOPES


def test_en_windows_no_se_cambian_permisos(auth, monkeypatch):
    monkeypatch.setattr(auth_module.os, "name", "nt")
    monkeypatch.setattr(
        type(auth._token_path),
        "chmod",
        lambda *_a: pytest.fail("chmod no debe llamarse en Windows"),
    )
    auth._save(FakeCreds())


def test_refresh_usa_un_transporte_http_real(auth):
    seen = []
    creds = FakeCreds(valid=False, expired=True)
    creds.refresh = lambda request: seen.append(request) or setattr(creds, "valid", True)
    auth._creds = creds
    auth.get_credentials()
    assert isinstance(seen[0], auth_module.Request)


def test_mensaje_exacto_de_sesion_revocada(auth):
    creds = FakeCreds(valid=False, expired=True)
    creds.refresh_error = RefreshError("invalid_grant")
    auth._creds = creds
    with pytest.raises(GoogleAuthError) as info:
        auth.get_credentials()
    assert str(info.value) == (
        "La sesión de Google ha caducado o se ha revocado. "
        "Pulsa «Cambiar de cuenta» para volver a conectar."
    )


def test_email_de_credenciales_sin_atributo_id_token():
    class Bare:
        pass

    assert _email_from_credentials(Bare()) is None  # type: ignore[arg-type]


def test_mensaje_exacto_sin_cliente(auth, no_bundled_client):
    with pytest.raises(GoogleAuthError) as info:
        auth.sign_in()
    assert str(info.value) == (
        "Esta compilación no tiene configurada la aplicación de Google. "
        "Consulta «Configurar Google» en la documentación."
    )


def test_mensaje_exacto_sin_permiso_de_calendario(auth, dummy_client, monkeypatch):
    fake_flow_runner(monkeypatch, creds=FakeCreds(scopes=["openid"]))
    with pytest.raises(GoogleAuthError) as info:
        auth.sign_in()
    assert str(info.value) == (
        "No se ha concedido acceso al calendario. Vuelve a pulsar "
        "«Conectar con Google» y deja marcada la casilla de Google Calendar."
    )


def test_sign_in_construye_el_flujo_con_el_cliente_y_los_permisos(auth, dummy_client, monkeypatch):
    calls = fake_flow_runner(monkeypatch, creds=FakeCreds())
    auth.sign_in()
    flow = calls["flow"]
    assert isinstance(flow, auth_module.InstalledAppFlow)
    assert flow.oauth2session.scope == auth_module.SCOPES
    assert flow.client_config["client_id"] == "dummy.apps.googleusercontent.com"


@pytest.fixture
def spy_server(monkeypatch):
    seen = {}
    real = auth_module.wsgiref.simple_server.make_server

    def make_server(host, port, app, **kwargs):
        seen.update(host=host, port=port, **kwargs)
        return real(host, port, app, **kwargs)

    monkeypatch.setattr(auth_module.wsgiref.simple_server, "make_server", make_server)
    return seen


def test_servidor_local_seguro_y_navegador_en_pestana_nueva(monkeypatch, spy_server):
    opened = []
    monkeypatch.setattr(
        auth_module.webbrowser, "open", lambda url, **kwargs: opened.append((url, kwargs))
    )
    thread, _, cancel = start_flow(FakeFlow())
    deadline = time.monotonic() + 3
    while not opened and time.monotonic() < deadline:
        time.sleep(0.02)
    cancel.set()
    thread.join(3)
    assert spy_server["host"] == "localhost"
    assert spy_server["port"] == 0
    assert spy_server["server_class"] is auth_module._LocalServer
    assert spy_server["handler_class"] is auth_module._RequestHandler
    assert opened[0][1] == {"new": 1, "autoraise": True}


def test_mensajes_exactos_de_cancelacion_tiempo_y_denegacion(browser, monkeypatch):
    thread, result, cancel = start_flow(FakeFlow())
    wait_for_browser(browser)
    cancel.set()
    thread.join(3)
    assert str(result["error"]) == "Conexión con Google cancelada."

    monkeypatch.setattr(auth_module, "SIGN_IN_TIMEOUT_SECONDS", 0.2)
    browser.clear()
    thread, result, _ = start_flow(FakeFlow())
    thread.join(5)
    assert str(result["error"]) == (
        "No se completó la autorización en el navegador a tiempo. "
        "Vuelve a pulsar «Conectar con Google»."
    )

    monkeypatch.setattr(auth_module, "SIGN_IN_TIMEOUT_SECONDS", 300)
    browser.clear()
    thread, result, _ = start_flow(FakeFlow())
    redirect = wait_for_browser(browser)
    urllib.request.urlopen(redirect + "?error=access_denied", timeout=5).read()
    thread.join(5)
    assert str(result["error"]) == "Has denegado el acceso en Google. No se ha conectado la cuenta."


def test_solo_se_cambia_el_esquema_de_la_url_de_respuesta(browser):
    """La URL de respuesta lleva otras URLs en los parámetros (scope): solo la
    primera aparición de «http» debe pasar a «https»."""
    flow = FakeFlow()
    thread, result, _ = start_flow(flow)
    redirect = wait_for_browser(browser)
    query = "?code=abc&scope=http://example.com/a+http://example.com/b"
    urllib.request.urlopen(redirect + query, timeout=5).read()
    thread.join(5)
    assert "creds" in result, result
    port = urlsplit(redirect).port
    assert flow.fetched == f"https://localhost:{port}/{query}"


def test_cancelar_justo_cuando_llega_la_respuesta_no_canjea_el_codigo(browser, monkeypatch):
    """Si el usuario cancela mientras Google redirige, no se completa la conexión."""
    cancel = threading.Event()

    class CancelOnResponse(auth_module._RedirectApp):
        def __call__(self, environ, start_response):
            response = super().__call__(environ, start_response)
            cancel.set()
            return response

    monkeypatch.setattr(auth_module, "_RedirectApp", CancelOnResponse)
    flow = FakeFlow()
    flow.fetch_token = MagicMock()
    thread, result, _ = start_flow(flow, cancel=cancel)
    redirect = wait_for_browser(browser)
    urllib.request.urlopen(redirect + "?code=abc", timeout=5).read()
    thread.join(3)
    assert isinstance(result.get("error"), SignInCancelled)
    assert str(result["error"]) == "Conexión con Google cancelada."
    flow.fetch_token.assert_not_called()
