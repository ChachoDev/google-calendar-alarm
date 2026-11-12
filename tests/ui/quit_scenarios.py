"""Escenarios de salida de la app, ejecutados cada uno en su propio proceso.

Al salir, Qt/PySide emiten ``aboutToQuit`` y limpian estado global; hacerlo
dentro del proceso de pytest contaminaría los tests siguientes. Uso:

    python tests/ui/quit_scenarios.py <escenario> <directorio de configuración>

Termina con código 0 si el escenario se comporta como se espera.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ["CALENDAR_ALARM_CONFIG_DIR"] = sys.argv[2]
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from PySide6.QtCore import QEvent, QTimer
from PySide6.QtWidgets import QApplication

from calendar_alarm import config as cfg
from calendar_alarm.app import CalendarAlarmApp
from calendar_alarm.models import CalendarEvent
from calendar_alarm.ui import util

TIMEOUT_EXIT = 99


def fail(message: str) -> int:
    print(f"FALLO: {message}", file=sys.stderr)
    return 1


def tray_quit(app: CalendarAlarmApp) -> int:
    now = datetime.now().astimezone()
    app.controller.on_events([CalendarEvent("q", "Reunión", "", "", now + timedelta(minutes=2))])
    if not app.controller.ringing:
        return fail("la alarma no llegó a sonar")
    quit_action = next(a for a in app.tray._menu.actions() if a.text() == "Salir")
    QTimer.singleShot(0, quit_action.trigger)
    QTimer.singleShot(3000, lambda: app.app.exit(TIMEOUT_EXIT))
    code = app.run()
    if code != 0:
        return fail(f"exec devolvió {code}")
    if app.worker.isRunning():
        return fail("el hilo de fondo sigue vivo")
    if app.audio.available:
        return fail("el audio sigue abierto")
    return 0


def system_quit(app: CalendarAlarmApp) -> int:
    """⌘Q / «Salir» del Dock: las ventanas solo se ocultan al cerrarlas, pero
    la salida pedida por el sistema debe completarse."""
    QTimer.singleShot(0, lambda: QApplication.sendEvent(app.app, QEvent(QEvent.Type.Quit)))
    QTimer.singleShot(3000, lambda: app.app.exit(TIMEOUT_EXIT))
    code = app.run()
    if code != 0:
        return fail(f"la salida del sistema se canceló (exec devolvió {code})")
    if not util.is_quitting():
        return fail("no se marcó la salida")
    return 0


def saves_config(app: CalendarAlarmApp) -> int:
    app.config.warn_minutes = 42
    QTimer.singleShot(0, app.quit)
    QTimer.singleShot(3000, lambda: app.app.exit(TIMEOUT_EXIT))
    if app.run() != 0:
        return fail("no salió")
    if cfg.load_config().warn_minutes != 42:
        return fail("no se guardó la configuración al salir")
    return 0


SCENARIOS = {"tray": tray_quit, "system": system_quit, "config": saves_config}

if __name__ == "__main__":
    sys.exit(SCENARIOS[sys.argv[1]](CalendarAlarmApp()))
