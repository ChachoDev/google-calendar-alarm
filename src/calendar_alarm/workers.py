from __future__ import annotations

import threading
from collections.abc import Callable

from PySide6.QtCore import QObject, Signal

from calendar_alarm.models import CalendarEvent


class BackgroundThread(QObject):
    """Base para trabajo en segundo plano que nunca bloquea la salida.

    Usa un hilo *daemon* de Python en lugar de ``QThread``: si al salir hay una
    llamada de red colgada, el hilo se abandona y el intérprete lo descarta.
    ``QThread.terminate()`` no sirve para esto: no puede interrumpir un hilo que
    ejecuta Python y puede dejar la aplicación bloqueada. Las señales se emiten
    desde el hilo de fondo y Qt las entrega en el hilo de la interfaz.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._thread: threading.Thread | None = None
        self._stop_requested = threading.Event()

    def start(self) -> None:
        if self.isRunning():
            return
        self._stop_requested.clear()
        self._thread = threading.Thread(target=self.run, name=type(self).__name__, daemon=True)
        self._thread.start()

    def isRunning(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def isInterruptionRequested(self) -> bool:
        return self._stop_requested.is_set()

    def requestInterruption(self) -> None:
        self._stop_requested.set()

    def wait(self, timeout_ms: int) -> bool:
        """Espera a que termine; True si terminó dentro del plazo."""
        if self._thread is None:
            return True
        self._thread.join(timeout_ms / 1000)
        return not self._thread.is_alive()

    def run(self) -> None:  # pragma: no cover - se sobrescribe
        raise NotImplementedError


class CalendarWorker(BackgroundThread):
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

    def stop(self, timeout_ms: int = 4000) -> bool:
        """Detiene el hilo sin bloquear indefinidamente la salida.

        Devuelve False si había una consulta de red en curso que no terminó a
        tiempo: el hilo queda abandonado y no volverá a emitir señales.
        """
        self.requestInterruption()
        self.wake()
        return self.wait(timeout_ms)

    def run(self) -> None:
        while not self.isInterruptionRequested():
            try:
                events = self._fetch_fn()
            except Exception as exc:  # red caída, token caducado, API con error...
                if not self.isInterruptionRequested():
                    self.error.emit(str(exc))
            else:
                if not self.isInterruptionRequested():
                    self.events_ready.emit(events)

            interval = max(5, int(self._interval_fn()))
            # Duerme hasta el siguiente ciclo o hasta que se le despierte.
            self._wake.wait(timeout=interval)
            self._wake.clear()
