"""Integración: la aplicación completa sin red ni cuenta de Google."""

from __future__ import annotations

import pytest

from calendar_alarm import app as app_module
from calendar_alarm.ui import util

pytestmark = pytest.mark.integration


def menu(app):
    return [a.text() for a in app.tray._menu.actions() if not a.isSeparator()]


@pytest.fixture
def calendar_app(qapp):
    qapp.setProperty(util._QUITTING_PROPERTY, False)
    instance = app_module.CalendarAlarmApp()
    yield instance
    instance._shutdown()
    instance.main_window.hide()
    instance.alarm_window.hide()
    qapp.removeEventFilter(instance._quit_watcher)
    qapp.setProperty(util._QUITTING_PROPERTY, False)


def test_arranque(calendar_app):
    assert calendar_app.main_window.isVisible()
    assert not calendar_app.alarm_window.isVisible()
    assert menu(calendar_app) == ["Salir"]
    assert calendar_app.worker.isRunning()


def test_sin_sesion_informa_de_que_hay_que_conectar(calendar_app, qtbot):
    qtbot.waitUntil(
        lambda: "Sin conectar" in calendar_app.main_window._events_status.text(), timeout=3000
    )


def test_alarma_completa_y_parada_desde_la_bandeja(calendar_app, make_event):
    event = make_event(summary="Reunión de prueba", description="Detalle", location="Sala 3")
    calendar_app.controller.on_events([event])

    assert calendar_app.controller.ringing
    assert calendar_app.alarm_window.isVisible()
    assert calendar_app.alarm_window._title.text() == "Reunión de prueba"
    assert not calendar_app.main_window.isVisible()
    assert menu(calendar_app) == ["Mostrar", "Parar alarma", "Salir"]

    stop = next(a for a in calendar_app.tray._menu.actions() if a.text() == "Parar alarma")
    stop.trigger()
    assert not calendar_app.controller.ringing
    assert not calendar_app.alarm_window.isVisible()
    assert menu(calendar_app) == ["Salir"]


def test_mostrar_con_alarma_abre_el_aviso(calendar_app, make_event):
    calendar_app.controller.on_events([make_event()])
    calendar_app.alarm_window.hide()
    calendar_app._show_appropriate()
    assert calendar_app.alarm_window.isVisible()


def test_mostrar_sin_alarma_abre_la_principal(calendar_app):
    calendar_app.main_window.hide()
    calendar_app._show_appropriate()
    assert calendar_app.main_window.isVisible()


def test_eventos_recibidos_actualizan_el_estado(calendar_app, make_event, monkeypatch):
    monkeypatch.setattr(type(calendar_app.auth), "is_authenticated", property(lambda _s: True))
    calendar_app._on_events([make_event(summary="Daily", minutes_from_now=120)])
    text = calendar_app.main_window._events_status.text()
    assert "1 evento(s)" in text and "«Daily»" in text
    calendar_app._on_events([])
    assert "No hay eventos" in calendar_app.main_window._events_status.text()


def test_error_de_consulta_se_muestra(calendar_app):
    calendar_app._on_fetch_error("Google caído")
    assert calendar_app.main_window._error_status.text() == "Google caído"
    assert "Sin conectar" in calendar_app.main_window._events_status.text()


def test_error_de_audio_se_muestra(calendar_app):
    calendar_app._on_audio_error("sin audio")
    assert calendar_app.main_window._error_status.text() == "sin audio"


def test_cambio_de_cuenta_olvida_avisos_y_para_la_alarma(calendar_app, make_event):
    event = make_event()
    calendar_app.controller.on_events([event])
    calendar_app._on_auth_changed()
    assert not calendar_app.controller.ringing
    calendar_app.controller.on_events([event])
    assert calendar_app.controller.ringing  # vuelve a avisar


@pytest.mark.parametrize(
    "scenario",
    [
        "tray",  # «Salir» del menú de la bandeja con una alarma sonando
        "system",  # ⌘Q / «Salir» del Dock / cierre de sesión
        "config",  # la configuración se guarda al salir
    ],
)
def test_salida_de_la_aplicacion(scenario, tmp_path):
    """Cada salida se prueba en un proceso propio (ver quit_scenarios.py)."""
    import subprocess
    import sys
    from pathlib import Path

    script = Path(__file__).with_name("quit_scenarios.py")
    result = subprocess.run(
        [sys.executable, str(script), scenario, str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr[-2000:]
