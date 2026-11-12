from __future__ import annotations

import threading
from collections.abc import Callable

from PySide6.QtCore import QThread, Signal

from calendar_alarm.models import CalendarEvent


class CalendarWorker(QThread):
    """Hilo de fondo: consulta Google Calendar periódicamente y emite los eventos.

    El hilo duerme entre consultas con un `threading.Event`, de modo que se
    puede interrumpir al instante al salir de la aplicación (`wake()` +
    `requestInterruption()`), sin bloquear jamás la interfaz gráfica.
    """

    events_ready = Signal(object)  # list[CalendarEvent]
    error = Signal(str)

    def __init__(
        self,
        fetch_fn: Callable[[], list[CalendarEvent]],
        interval_fn: Callable[[], int],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._fetch_fn = fetch_fn
        self._interval_fn = interval_fn
        self._wake = threading.Event()

    def wake(self) -> None:
        """Despierta al hilo para que consulte de inmediato (cambios del usuario)."""
        self._wake.set()

    def stop(self, timeout_ms: int = 4000) -> None:
        """Detiene el hilo sin bloquear indefinidamente la salida."""
        self.requestInterruption()
        self.wake()
        if not self.wait(timeout_ms):
            # Hay una consulta de red en curso: al salir no se espera más.
            self.terminate()
            self.wait(1000)

    def run(self) -> None:
        while not self.isInterruptionRequested():
            try:
                events = self._fetch_fn()
            except Exception as exc:  # red caída, token caducado, API con error...
                self.error.emit(str(exc))
            else:
                self.events_ready.emit(events)

            interval = max(5, int(self._interval_fn()))
            # Dormir en intervalos cortos para poder salir rápido al cerrar.
            self._wake.wait(timeout=interval)
            self._wake.clear()
