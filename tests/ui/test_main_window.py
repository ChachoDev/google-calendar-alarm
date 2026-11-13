from __future__ import annotations

import threading

import pytest
from PySide6.QtCore import Qt

from calendar_alarm import config as cfg
from calendar_alarm.auth import GoogleAuthError, SignInCancelled
from calendar_alarm.config import Config
from calendar_alarm.ui import main_window as mw_module
from calendar_alarm.ui import util
from calendar_alarm.ui.main_window import MainWindow


class FakeAuth:
    """GoogleAuth de mentira: sign_in se controla desde el test."""

    def __init__(self, authenticated=False, email=None):
        self.is_authenticated = authenticated
        self.account_email = email
        self.signed_out = False
        self.started = threading.Event()
        self.release = threading.Event()
        self.result: object = "nuevo@example.com"

    def sign_in(self, *, select_account=True, cancel=None):
        self.started.set()
        while not self.release.wait(0.02):
            if cancel is not None and cancel.is_set():
                raise SignInCancelled("cancelado")
        if isinstance(self.result, Exception):
            raise self.result
        self.is_authenticated = True
        self.account_email = self.result
        return self.result

    def sign_out(self):
        self.signed_out = True
        self.is_authenticated = False
        self.account_email = None


class FakeAudio:
    def __init__(self, ok=True):
        self.ok = ok
        self.tested: list[str] = []
        self.last_error = None if ok else "sin altavoces"

    def test(self, path):
        self.tested.append(path)
        return self.ok


@pytest.fixture
def make_window(qtbot, monkeypatch):
    monkeypatch.setattr(mw_module, "is_configured", lambda: True)

    def factory(config=None, auth=None, audio=None):
        window = MainWindow(config or Config(), auth or FakeAuth(), audio or FakeAudio())  # type: ignore[arg-type]
        qtbot.addWidget(window)
        window.show()
        return window

    return factory


def status(window):
    return window._auth_status.text()


def test_estado_inicial_desconectado(make_window):
    w = make_window()
    assert "No conectada" in status(w)
    assert w._btn_connect.isVisible()
    assert not w._btn_change.isVisible()
    assert not w._btn_logout.isVisible()
    assert not w._btn_cancel.isVisible()


def test_estado_inicial_conectado(make_window):
    w = make_window(auth=FakeAuth(authenticated=True, email="ana@example.com"))
    assert "Conectado como ana@example.com" in status(w)
    assert not w._btn_connect.isVisible()
    assert w._btn_change.isVisible()
    assert w._btn_logout.isVisible()


def test_conectado_sin_email(make_window):
    w = make_window(auth=FakeAuth(authenticated=True))
    assert status(w).endswith("Conectada")


def test_conexion_correcta(make_window, qtbot):
    auth = FakeAuth()
    w = make_window(auth=auth)
    with qtbot.waitSignal(w.auth_changed, timeout=3000):
        qtbot.mouseClick(w._btn_connect, Qt.MouseButton.LeftButton)
        assert auth.started.wait(2)
        assert w._btn_cancel.isVisible()
        assert not w._btn_connect.isEnabled()
        assert "Esperando autorización" in status(w)
        auth.release.set()
    assert "nuevo@example.com" in status(w)
    assert not w._btn_cancel.isVisible()
    assert "Consultando" in w._events_status.text()
    assert w._sign_in_worker is None


def test_cancelar_la_espera(make_window, qtbot):
    auth = FakeAuth()
    w = make_window(auth=auth)
    qtbot.mouseClick(w._btn_connect, Qt.MouseButton.LeftButton)
    assert auth.started.wait(2)
    with qtbot.assertNotEmitted(w.auth_changed):
        qtbot.mouseClick(w._btn_cancel, Qt.MouseButton.LeftButton)
        assert not w._btn_cancel.isEnabled()  # evita doble cancelación
        qtbot.waitUntil(lambda: w._sign_in_worker is None, timeout=2000)
    assert w._btn_connect.isEnabled()
    assert not w._btn_cancel.isVisible()
    assert "No conectada" in status(w)
    assert w._events_status.text() == "Conexión con Google cancelada."
    assert not w._auth_error.isVisible()


def test_tras_cancelar_se_puede_reintentar(make_window, qtbot):
    auth = FakeAuth()
    w = make_window(auth=auth)
    qtbot.mouseClick(w._btn_connect, Qt.MouseButton.LeftButton)
    assert auth.started.wait(2)
    qtbot.mouseClick(w._btn_cancel, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: w._sign_in_worker is None, timeout=2000)

    auth.started.clear()
    auth.release.set()
    with qtbot.waitSignal(w.auth_changed, timeout=3000):
        qtbot.mouseClick(w._btn_connect, Qt.MouseButton.LeftButton)
    assert auth.is_authenticated


def test_cancelar_sin_espera_no_hace_nada(make_window):
    w = make_window()
    w._on_cancel_sign_in()
    assert "No conectada" in status(w)


def test_error_de_autenticacion_se_muestra(make_window, qtbot):
    auth = FakeAuth()
    auth.result = GoogleAuthError("Has denegado el acceso en Google.")
    auth.release.set()
    w = make_window(auth=auth)
    qtbot.mouseClick(w._btn_connect, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: w._sign_in_worker is None, timeout=3000)
    assert w._auth_error.isVisible()
    assert w._auth_error.text() == "Has denegado el acceso en Google."
    assert w._btn_connect.isEnabled()


def test_error_inesperado_se_muestra(make_window, qtbot):
    auth = FakeAuth()
    auth.result = ValueError("raro")
    auth.release.set()
    w = make_window(auth=auth)
    qtbot.mouseClick(w._btn_connect, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: w._sign_in_worker is None, timeout=3000)
    assert w._auth_error.text() == "Error inesperado al autenticar: raro"


def test_sin_cliente_configurado_no_abre_el_navegador(make_window, monkeypatch):
    auth = FakeAuth()
    w = make_window(auth=auth)
    monkeypatch.setattr(mw_module, "is_configured", lambda: False)
    w._on_sign_in()
    assert not auth.started.is_set()
    assert "no incluye la configuración de Google" in w._auth_error.text()


def test_cambiar_de_cuenta_inicia_la_conexion(make_window, qtbot):
    auth = FakeAuth(authenticated=True, email="a@example.com")
    auth.release.set()
    w = make_window(auth=auth)
    with qtbot.waitSignal(w.auth_changed, timeout=3000):
        qtbot.mouseClick(w._btn_change, Qt.MouseButton.LeftButton)
    assert "nuevo@example.com" in status(w)


def test_cerrar_sesion(make_window, qtbot):
    auth = FakeAuth(authenticated=True, email="a@example.com")
    w = make_window(auth=auth)
    with qtbot.waitSignal(w.auth_changed, timeout=1000):
        qtbot.mouseClick(w._btn_logout, Qt.MouseButton.LeftButton)
    assert auth.signed_out
    assert "No conectada" in status(w)
    assert "Sesión cerrada" in w._events_status.text()


def test_shutdown_cancela_la_espera_sin_bloquear(make_window, qtbot):
    import time

    auth = FakeAuth()
    w = make_window(auth=auth)
    qtbot.mouseClick(w._btn_connect, Qt.MouseButton.LeftButton)
    assert auth.started.wait(2)
    started = time.monotonic()
    w.shutdown()
    assert time.monotonic() - started < 1.0
    assert not w._sign_in_worker.isRunning()


def test_shutdown_sin_espera(make_window):
    make_window().shutdown()


def test_cambiar_margen_guarda_configuracion(make_window):
    config = Config()
    w = make_window(config=config)
    w._hours.setValue(2)
    w._minutes.setValue(30)
    assert (config.warn_hours, config.warn_minutes) == (2, 30)
    assert cfg.load_config().warn_hours == 2
    assert cfg.load_config().warn_minutes == 30


def test_rango_de_los_selectores(make_window):
    w = make_window()
    assert (w._hours.minimum(), w._hours.maximum()) == (0, 23)
    assert (w._minutes.minimum(), w._minutes.maximum()) == (1, 59)
    w._hours.setValue(2)
    assert (w._minutes.minimum(), w._minutes.maximum()) == (0, 59)


def test_minutos_minimos_dependen_de_las_horas(make_window):
    w = make_window(config=Config(warn_hours=0, warn_minutes=5))
    assert w._minutes.minimum() == 1
    w._hours.setValue(1)
    assert w._minutes.minimum() == 0
    w._minutes.setValue(0)
    w._hours.setValue(0)
    assert w._minutes.value() == 1
    assert w.config.warn_minutes == 1


def test_intervalo_de_consulta_en_minutos(make_window):
    config = Config(poll_minutes=10)
    w = make_window(config=config)
    assert (w._poll.minimum(), w._poll.maximum()) == (5, 60)
    assert w._poll.suffix() == " min"
    assert w._poll.value() == 10
    w._poll.setValue(30)
    assert config.poll_minutes == 30
    assert cfg.load_config().poll_minutes == 30


def test_intervalo_fuera_de_rango_se_recorta(make_window):
    w = make_window(config=Config(poll_minutes=1))
    assert w._poll.value() == 5
    w2 = make_window(config=Config(poll_minutes=999))
    assert w2._poll.value() == 60


def test_elegir_sonido(make_window, monkeypatch, tmp_path):
    config = Config()
    w = make_window(config=config)
    chosen = str(tmp_path / "mi.ogg")
    seen = {}

    def fake_dialog(parent, title, start_dir, filt):
        seen.update(start_dir=start_dir, filt=filt)
        return chosen, ""

    monkeypatch.setattr(mw_module.QFileDialog, "getOpenFileName", fake_dialog)
    w._on_browse_sound()
    assert config.sound_path == chosen
    assert seen["start_dir"] == ""
    assert "*.wav" in seen["filt"] and "*.mp3" in seen["filt"]
    assert w._sound_label.toolTip() == chosen
    assert cfg.load_config().sound_path == chosen

    w._on_browse_sound()
    assert seen["start_dir"] == str(tmp_path)


def test_cancelar_dialogo_de_sonido_no_cambia_nada(make_window, monkeypatch):
    config = Config(sound_path="/x/a.wav")
    w = make_window(config=config)
    monkeypatch.setattr(mw_module.QFileDialog, "getOpenFileName", lambda *a: ("", ""))
    w._on_browse_sound()
    assert config.sound_path == "/x/a.wav"


def test_volver_al_sonido_por_defecto(make_window):
    config = Config(sound_path="/x/a.wav")
    w = make_window(config=config)
    w._on_default_sound()
    assert config.sound_path == ""
    assert w._sound_label.toolTip().endswith("(por defecto)")


def test_probar_sonido(make_window):
    audio = FakeAudio()
    config = Config(sound_path="/x/a.wav")
    w = make_window(config=config, audio=audio)
    w._on_test_sound()
    assert audio.tested == ["/x/a.wav"]
    assert not w._error_status.isVisible()


def test_probar_sonido_con_error(make_window):
    w = make_window(audio=FakeAudio(ok=False))
    w._on_test_sound()
    assert w._error_status.isVisible()
    assert w._error_status.text() == "sin altavoces"


def test_mensajes_de_estado(make_window):
    w = make_window()
    w.show_events_status("3 eventos")
    assert w._events_status.text() == "3 eventos"
    w.show_error("fallo")
    assert w._error_status.isVisible()
    w.hide_error()
    assert not w._error_status.isVisible()


def test_boton_salir_emite_senal(make_window, qtbot):
    from PySide6.QtWidgets import QPushButton

    w = make_window()
    quit_btn = next(b for b in w.findChildren(QPushButton) if b.text() == "Salir")
    with qtbot.waitSignal(w.quit_requested, timeout=1000):
        qtbot.mouseClick(quit_btn, Qt.MouseButton.LeftButton)


def test_cerrar_ventana_solo_la_oculta(make_window):
    w = make_window()
    assert w.close() is False
    assert not w.isVisible()


def test_cerrar_al_salir_se_acepta(make_window, qapp):
    w = make_window()
    util.mark_quitting()
    try:
        assert w.close() is True
    finally:
        qapp.setProperty(util._QUITTING_PROPERTY, False)
