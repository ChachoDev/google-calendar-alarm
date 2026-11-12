from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from PySide6.QtCore import Qt

from calendar_alarm.ui import alarm_window as aw_module
from calendar_alarm.ui import util
from calendar_alarm.ui.alarm_window import AlarmWindow


@pytest.fixture
def window(qtbot):
    w = AlarmWindow()
    qtbot.addWidget(w)
    return w


def test_muestra_los_datos_del_evento(window, make_event):
    start = datetime(2026, 5, 4, 10, 0).astimezone()
    event = make_event(
        summary="Revisión trimestral",
        description="Traer las cifras",
        location="Sala Norte",
        start=start,
        end=start + timedelta(hours=1),
    )
    window.show_event(event)
    assert window.isVisible()
    assert window._title.text() == "Revisión trimestral"
    assert window._description.text() == "Traer las cifras"
    assert window._location.text() == "Ubicación: Sala Norte"
    assert window._location.isVisible()
    assert window._when.text() == event.schedule_str()


def test_sin_ubicacion_ni_descripcion(window, make_event):
    window.show_event(make_event(summary="", description="", location=""))
    assert window._title.text() == "(Sin título)"
    assert window._description.text() == "Sin descripción."
    assert not window._location.isVisible()


def test_tamano_dentro_de_la_pantalla(window, make_event):
    window.show_event(make_event())
    available = window.screen().availableGeometry()
    assert window.width() <= max(available.width(), window.minimumSizeHint().width())
    assert window.width() >= window.minimumWidth()


@pytest.mark.parametrize("key", [Qt.Key.Key_Escape, Qt.Key.Key_Return, Qt.Key.Key_Enter])
def test_teclas_paran_la_alarma(window, qtbot, make_event, key):
    window.show_event(make_event())
    with qtbot.waitSignal(window.stop_requested, timeout=1000):
        qtbot.keyClick(window, key)


def test_otra_tecla_no_para(window, qtbot, make_event):
    window.show_event(make_event())
    with qtbot.assertNotEmitted(window.stop_requested):
        qtbot.keyClick(window, Qt.Key.Key_A)


def test_boton_parar(window, qtbot, make_event):
    window.show_event(make_event())
    with qtbot.waitSignal(window.stop_requested, timeout=1000):
        qtbot.mouseClick(window._stop_btn, Qt.MouseButton.LeftButton)


def test_cerrar_oculta_pero_no_para(window, qtbot, make_event):
    window.show_event(make_event())
    with qtbot.assertNotEmitted(window.stop_requested):
        window.close()
    assert not window.isVisible()


def test_cerrar_al_salir_la_app_se_acepta(window, make_event, qapp):
    window.show_event(make_event())
    util.mark_quitting()
    try:
        assert window.close() is True
    finally:
        qapp.setProperty(util._QUITTING_PROPERTY, False)


def test_parpadeo_solo_mientras_es_visible(window, qtbot, make_event):
    assert not window._pulse.isActive()
    window.show_event(make_event())
    assert window._pulse.isActive()
    qtbot.waitUntil(lambda: window._badge.property("alt") is True, timeout=2000)
    window.hide()
    assert not window._pulse.isActive()
    assert window._badge.property("alt") is False


def test_en_hyprland_programa_flotar_centrar_y_fijar(window, qtbot, make_event, monkeypatch):
    calls = []
    monkeypatch.setattr(aw_module, "is_hyprland", lambda: True)
    monkeypatch.setattr(aw_module, "float_alarm_window", lambda t: calls.append(("float", t)))
    monkeypatch.setattr(
        aw_module, "resize_alarm_window", lambda t, w, h: calls.append(("resize", t)) or True
    )
    monkeypatch.setattr(aw_module, "center_alarm_window", lambda t: calls.append(("center", t)))
    monkeypatch.setattr(aw_module, "pin_alarm_window", lambda t: calls.append(("pin", t)))
    window.show_event(make_event())
    qtbot.waitUntil(lambda: len(calls) == 4, timeout=2000)
    title = window.windowTitle()
    assert calls == [("float", title), ("resize", title), ("center", title), ("pin", title)]


def test_fuera_de_hyprland_no_llama_a_hyprctl(window, qtbot, make_event, monkeypatch):
    monkeypatch.setattr(aw_module, "is_hyprland", lambda: False)
    monkeypatch.setattr(aw_module, "float_alarm_window", lambda t: pytest.fail("no debe llamarse"))
    window.show_event(make_event())
    qtbot.wait(500)


def test_si_hyprctl_no_redimensiona_usa_qt(window, qtbot, make_event, monkeypatch):
    monkeypatch.setattr(aw_module, "is_hyprland", lambda: True)
    for name in ("float_alarm_window", "center_alarm_window", "pin_alarm_window"):
        monkeypatch.setattr(aw_module, name, lambda t: None)
    monkeypatch.setattr(aw_module, "resize_alarm_window", lambda t, w, h: False)
    fallback = []
    monkeypatch.setattr(window, "_resize_centered", lambda: fallback.append(True))
    window.show_event(make_event())
    qtbot.waitUntil(lambda: fallback == [True], timeout=2000)


def test_acciones_de_hyprland_no_se_aplican_si_la_ventana_se_oculto(window, monkeypatch):
    monkeypatch.setattr(aw_module, "float_alarm_window", lambda t: pytest.fail("oculta"))
    monkeypatch.setattr(aw_module, "resize_alarm_window", lambda *a: pytest.fail("oculta"))
    window._float_on_hyprland()
    window._center_and_pin()
    window._resize_centered()


def test_desired_size_respeta_la_pantalla(window):
    width, height = window._desired_size()
    assert width >= window.minimumSizeHint().width()
    assert height >= window.minimumSizeHint().height()
