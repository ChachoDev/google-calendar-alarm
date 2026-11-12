from __future__ import annotations

from datetime import datetime, timedelta

from PySide6.QtCore import QObject, Signal

from calendar_alarm.audio import AudioPlayer
from calendar_alarm.config import Config
from calendar_alarm.models import CalendarEvent


class AlarmController(QObject):
    """Control de alarmas: decide cuándo suena y cuándo se detiene.

    Esta capa no conoce nada de la presentación (ventanas, bandeja, menús).
    Emite señales y son la capa de UI quien decide qué mostrar.
    Estados: IDLE (silencio) <-> RINGING (sonando).
    """

    alarm_started = Signal(object)  # CalendarEvent
    alarm_stopped = Signal()
    audio_error = Signal(str)

    def __init__(self, audio: AudioPlayer, config: Config, parent=None) -> None:
        super().__init__(parent)
        self._audio = audio
        self._config = config
        self._ringing = False
        self._current: CalendarEvent | None = None
        # Avisos ya lanzados, por evento y hora de inicio: no se repite el mismo
        # aviso, pero si el evento se mueve a otra hora vuelve a avisar.
        self._handled: set[str] = set()

    # ------------------------------------------------------------- estado
    @property
    def ringing(self) -> bool:
        return self._ringing

    @property
    def current_event(self) -> CalendarEvent | None:
        return self._current

    # ------------------------------------------------------------- eventos
    def on_events(self, events: list[CalendarEvent]) -> None:
        """Comprueba en cada consulta si toca lanzar la alarma."""
        if self._ringing:
            return  # ya está sonando: no se reengancha hasta pararla

        now = datetime.now().astimezone()
        warn = self._config.warn_delta
        # Margen para no "perder" el aviso entre dos consultas consecutivas:
        # si el evento empezó hace menos de un ciclo de consulta, aún avisa.
        grace = timedelta(seconds=max(self._config.poll_interval, 30))

        candidates = [
            event
            for event in events
            if _alarm_key(event) not in self._handled
            and (event.start - warn) <= now <= (event.start + grace)
        ]
        if not candidates:
            return

        self._start(min(candidates, key=lambda e: e.start))

    def _start(self, event: CalendarEvent) -> None:
        self._ringing = True
        self._current = event
        self._handled.add(_alarm_key(event))

        if not self._audio.play_loop(self._config.resolved_sound_path):
            self.audio_error.emit(
                self._audio.last_error or "No se pudo reproducir el sonido de la alarma."
            )
        self.alarm_started.emit(event)

    def stop(self) -> None:
        """Detiene la alarma (sonido + estado). Idempotente."""
        if not self._ringing:
            return
        self._ringing = False
        self._current = None
        self._audio.stop()
        self.alarm_stopped.emit()

    def forget_handled(self) -> None:
        """Permite volver a avisar por eventos ya tratados (cambio de cuenta)."""
        self._handled.clear()


def _alarm_key(event: CalendarEvent) -> str:
    return f"{event.id}@{event.start.isoformat()}"
