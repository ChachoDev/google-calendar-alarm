from __future__ import annotations

import pytest
from PySide6.QtWidgets import QSystemTrayIcon

from calendar_alarm.ui.tray import TrayIcon


def texts(tray):
    return [a.text() for a in tray._menu.actions() if not a.isSeparator()]


@pytest.fixture
def tray(qapp):
    t = TrayIcon()
    yield t
    t.hide()


def test_menu_en_reposo(tray):
    assert texts(tray) == ["Salir"]


def test_menu_sonando_y_vuelta_a_reposo(tray):
    tray.set_ringing(True)
    assert texts(tray) == ["Mostrar", "Parar alarma", "Salir"]
    tray.set_ringing(False)
    assert texts(tray) == ["Salir"]


def test_set_ringing_repetido_no_reconstruye(tray):
    menu = tray._menu
    tray.set_ringing(False)
    assert tray._menu is menu


def test_icono_cambia_de_color_al_sonar(tray):
    idle = tray._tray.icon().pixmap(32).toImage()
    tray.set_ringing(True)
    ringing = tray._tray.icon().pixmap(32).toImage()
    assert idle != ringing


@pytest.mark.parametrize(
    ("label", "signal"),
    [
        ("Mostrar", "show_requested"),
        ("Parar alarma", "stop_requested"),
        ("Salir", "quit_requested"),
    ],
)
def test_acciones_del_menu_emiten_senales(tray, qtbot, label, signal):
    tray.set_ringing(True)
    action = next(a for a in tray._menu.actions() if a.text() == label)
    with qtbot.waitSignal(getattr(tray, signal), timeout=1000):
        action.trigger()


@pytest.mark.parametrize(
    "reason",
    [QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick],
)
def test_clic_en_el_icono_pide_mostrar(tray, qtbot, reason):
    with qtbot.waitSignal(tray.show_requested, timeout=1000):
        tray._on_activated(reason)


def test_clic_derecho_no_pide_mostrar(tray, qtbot):
    with qtbot.assertNotEmitted(tray.show_requested):
        tray._on_activated(QSystemTrayIcon.ActivationReason.Context)


def test_clic_en_la_notificacion_pide_mostrar(tray, qtbot):
    with qtbot.waitSignal(tray.show_requested, timeout=1000):
        tray._tray.messageClicked.emit()


def test_show_message_no_falla(tray):
    tray.show_message("Título", "Mensaje")
