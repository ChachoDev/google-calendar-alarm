"""Punto de entrada usado por PyInstaller (y equivalente a `calendar-alarm`)."""

from __future__ import annotations

import os
import sys


def _prepare_frozen_runtime() -> None:
    # Ejecutables sin consola (Windows --windowed, .app de macOS): stdout y
    # stderr pueden ser None y cualquier librería que escriba en ellos fallaría.
    for name in ("stdout", "stderr"):
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))  # noqa: SIM115

    # Evita el mensaje de bienvenida que pygame imprime al importarse.
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

    if sys.platform == "win32":
        # Identidad propia en la barra de tareas: usa el icono de la app en
        # lugar del de Python y agrupa bien sus ventanas.
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "CalendarAlarm.CalendarAlarm"
            )
        except Exception:
            pass


_prepare_frozen_runtime()

from calendar_alarm.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
