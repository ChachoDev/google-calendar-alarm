from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CalendarEvent:
    """Representación normalizada de un evento de Google Calendar."""

    id: str
    summary: str
    description: str
    location: str
    start: datetime  # horario local, con zona horaria
    end: datetime | None = None

    @property
    def start_str(self) -> str:
        return self.start.strftime("%H:%M")

    @property
    def end_str(self) -> str:
        return self.end.strftime("%H:%M") if self.end else "--:--"

    @property
    def date_str(self) -> str:
        return self.start.strftime("%d/%m/%Y")

    def schedule_str(self) -> str:
        if self.end and self.end.date() == self.start.date():
            return f"{self.date_str} · {self.start_str} – {self.end_str}"
        if self.end:
            return f"{self.date_str} · {self.start_str} – {self.end.strftime('%d/%m/%Y %H:%M')}"
        return f"{self.date_str} · {self.start_str}"
