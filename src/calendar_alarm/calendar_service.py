from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httplib2
from google_auth_httplib2 import AuthorizedHttp
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from calendar_alarm.models import CalendarEvent


class CalendarService:
    """Consulta puntual a la API de Google Calendar (ejecutada en el hilo de fondo)."""

    def __init__(self, credentials) -> None:
        # Timeout acotado: permite cerrar la aplicación sin esperas eternas
        # si la red se queda colgada a mitad de una consulta.
        http = AuthorizedHttp(credentials, http=httplib2.Http(timeout=30))
        self._service = build("calendar", "v3", http=http, cache_discovery=False)

    def upcoming_events(self, *, hours: int = 24, max_results: int = 100) -> list[CalendarEvent]:
        """Eventos con hora exacta en las próximas `hours` horas (horario local).

        Los eventos de todo el día se ignoran: no tienen una hora a la que
        programar una alarma con margen.
        """
        now = datetime.now(timezone.utc)
        try:
            result = (
                self._service.events()
                .list(
                    calendarId="primary",
                    timeMin=now.isoformat(),
                    timeMax=(now + timedelta(hours=hours)).isoformat(),
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=max_results,
                )
                .execute()
            )
        except HttpError as exc:
            raise RuntimeError(f"Google Calendar respondió un error: {exc}") from exc

        events: list[CalendarEvent] = []
        for item in result.get("items", []):
            parsed = _parse_event(item)
            if parsed is not None:
                events.append(parsed)
        events.sort(key=lambda e: e.start)
        return events


def _parse_event(item: dict) -> CalendarEvent | None:
    start_raw = item.get("start", {})
    end_raw = item.get("end", {})
    if "dateTime" not in start_raw:
        return None  # evento de todo el día: sin hora exacta, se omite
    try:
        start = _to_local(start_raw["dateTime"])
        end = _to_local(end_raw["dateTime"]) if "dateTime" in end_raw else None
    except ValueError:
        return None
    return CalendarEvent(
        id=item.get("id", ""),
        summary=item.get("summary", "(Sin título)"),
        description=(item.get("description") or "").strip(),
        location=(item.get("location") or "").strip(),
        start=start,
        end=end,
    )


def _to_local(value: str) -> datetime:
    # Desde Python 3.11 fromisoformat entiende el sufijo «Z» (UTC).
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone()


class EventFetcher:
    """Callable usado por el hilo de fondo: obtiene los próximos eventos.

    Cachéa el cliente de la API para no repetir la descubrimiento del
    servicio en cada consulta y se invalida solo cuando cambia la cuenta.
    """

    def __init__(self, auth) -> None:
        self._auth = auth
        self._creds_ref = None
        self._service: CalendarService | None = None

    def __call__(self, hours: int = 24) -> list[CalendarEvent]:
        creds = self._auth.get_credentials()
        if creds is None:
            self._creds_ref = None
            self._service = None
            return []
        if self._service is None or self._creds_ref is not creds:
            self._service = CalendarService(creds)
            self._creds_ref = creds
        return self._service.upcoming_events(hours=hours)
