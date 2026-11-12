"""Prueba de humo: arranca la app (sin red ni Google), simula alarmas y verifica.

Uso:  uv run python scripts/smoke_test.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import wave
from datetime import datetime, timedelta
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
# Configuración temporal: la prueba no toca la configuración ni el token reales.
os.environ["CALENDAR_ALARM_CONFIG_DIR"] = tempfile.mkdtemp(prefix="calendar-alarm-smoke-")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QTimer

from calendar_alarm.app import CalendarAlarmApp
from calendar_alarm.config import Config, default_sound_path
from calendar_alarm.models import CalendarEvent

FAILURES: list[str] = []


def check(condition: bool, message: str) -> None:
    print(f"  {'OK ' if condition else 'FAIL'}  {message}")
    if not condition:
        FAILURES.append(message)


def menu_texts(tray) -> list[str]:
    menu = tray._menu  # inspección interna, solo para el test
    return [action.text() for action in menu.actions() if not action.isSeparator()]


def main() -> int:
    print("== Configuración ==")
    default = Config()
    check(
        default.warn_minutes == 5 and default.warn_hours == 0,
        "el margen por defecto es de 5 minutos",
    )
    sound = Path(default_sound_path())
    check(sound.is_file(), f"el sonido por defecto existe ({sound.name})")
    if sound.is_file():
        with wave.open(str(sound), "rb") as wav:
            check(wav.getnframes() > 0, "el sonido por defecto es un WAV válido")

    print("== Arranque ==")
    app = CalendarAlarmApp()
    check(app.main_window.isVisible(), "la ventana principal está visible")
    check(menu_texts(app.tray) == ["Salir"], "menú en reposo: solo «Salir»")
    check(not app.controller.ringing, "arranca sin alarma activa")
    check(app.worker.isRunning(), "el hilo de fondo de consultas está en marcha")

    print("== Alarma detectada ==")
    now = datetime.now().astimezone()
    event = CalendarEvent(
        id="smoke-1",
        summary="Reunión de prueba",
        description="Descripción relevante del evento de prueba.",
        location="Sala 3",
        start=now + timedelta(minutes=3),  # dentro del margen de 5 min
        end=now + timedelta(minutes=33),
    )
    app.controller.on_events([event])
    check(app.controller.ringing, "la alarma se activa dentro del margen")
    check(app.alarm_window.isVisible(), "la ventana de alarma prominente es visible")
    check(
        app.alarm_window._title.text() == "Reunión de prueba",
        "la ventana de alarma muestra el título del evento",
    )
    check(
        "Descripción relevante" in app.alarm_window._description.text(),
        "la ventana de alarma muestra la descripción",
    )
    check(not app.main_window.isVisible(), "la ventana principal se minimiza")
    check(
        menu_texts(app.tray) == ["Mostrar", "Parar alarma", "Salir"],
        "menú sonando: «Mostrar», «Parar alarma» y «Salir»",
    )

    print("== Evento ya avisado no reengancha ==")
    app.controller.on_events([event])
    check(
        app.controller.ringing and app.controller.current_event is event,
        "no vuelve a lanzar el mismo evento",
    )

    print("== Detener desde el menú de bandeja ==")
    stop_action = next(a for a in app.tray._menu.actions() if a.text() == "Parar alarma")
    stop_action.trigger()
    check(not app.controller.ringing, "«Parar alarma» detiene la alarma")
    check(not app.alarm_window.isVisible(), "la ventana de alarma se cierra")
    check(menu_texts(app.tray) == ["Salir"], "vuelve al menú con solo «Salir»")

    print("== Alarma tardía (evento ya empezado, dentro de la tolerancia) ==")
    late_event = CalendarEvent(
        id="smoke-2",
        summary="Evento tardío",
        description="",
        location="",
        start=now - timedelta(seconds=10),
    )
    app.controller.on_events([late_event])
    check(app.controller.ringing, "avisa también si el evento acaba de empezar")
    app.controller.stop()

    print("== Margen insuficiente no dispara ==")
    far_event = CalendarEvent(
        id="smoke-3",
        summary="Lejos",
        description="",
        location="",
        start=now + timedelta(minutes=30),
    )
    app.controller.on_events([far_event])
    check(not app.controller.ringing, "no suena 30 minutos antes con margen de 5")

    print("== Salida completa desde «Salir» ==")
    quit_action = next(a for a in app.tray._menu.actions() if a.text() == "Salir")
    quit_action.trigger()  # -> app.quit() -> aboutToQuit -> _shutdown()
    QTimer.singleShot(3000, app.quit)  # red de seguridad
    code = app.app.exec()

    check(code == 0, "la aplicación termina con código 0")
    check(not app.worker.isRunning(), "el hilo de fondo se ha detenido")
    check(not app.audio.available, "el audio se ha cerrado por completo")

    print()
    if FAILURES:
        print(f"{len(FAILURES)} comprobación(es) fallida(s):")
        for failure in FAILURES:
            print(f"  - {failure}")
        return 1
    print("Todas las comprobaciones han pasado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
