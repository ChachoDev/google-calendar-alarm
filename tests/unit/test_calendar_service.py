from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from googleapiclient.errors import HttpError

from calendar_alarm import calendar_service as cs


def item(**overrides):
    base = {
        "id": "abc",
        "summary": "Daily",
        "description": "  notas  ",
        "location": " Sala 1 ",
        "start": {"dateTime": "2026-05-04T10:00:00+02:00"},
        "end": {"dateTime": "2026-05-04T10:15:00+02:00"},
    }
    base.update(overrides)
    return base


def test_parse_evento_completo():
    e = cs._parse_event(item())
    assert e is not None
    assert e.id == "abc"
    assert e.summary == "Daily"
    assert e.description == "notas"
    assert e.location == "Sala 1"
    assert e.start == datetime(2026, 5, 4, 8, 0, tzinfo=timezone.utc)
    assert e.end == datetime(2026, 5, 4, 8, 15, tzinfo=timezone.utc)


def test_parse_convierte_a_hora_local():
    e = cs._parse_event(item())
    assert e is not None
    local_offset = e.start.astimezone().utcoffset()
    assert e.start.utcoffset() == local_offset


def test_parse_ignora_eventos_de_todo_el_dia():
    assert cs._parse_event(item(start={"date": "2026-05-04"}, end={"date": "2026-05-05"})) is None


def test_parse_sin_start_se_ignora():
    data = item()
    del data["start"]
    assert cs._parse_event(data) is None


def test_parse_valores_por_defecto():
    e = cs._parse_event({"start": {"dateTime": "2026-05-04T10:00:00Z"}})
    assert e is not None
    assert e.id == ""
    assert e.summary == "(Sin título)"
    assert e.description == ""
    assert e.location == ""
    assert e.end is None


def test_parse_descripcion_y_ubicacion_nulas():
    e = cs._parse_event(item(description=None, location=None))
    assert e is not None
    assert (e.description, e.location) == ("", "")


def test_parse_fin_de_todo_el_dia_queda_sin_fin():
    e = cs._parse_event(item(end={"date": "2026-05-05"}))
    assert e is not None
    assert e.end is None


def test_parse_fecha_invalida_se_ignora():
    assert cs._parse_event(item(start={"dateTime": "mañana"})) is None


def test_to_local_acepta_z_y_sin_zona():
    z = cs._to_local("2026-05-04T08:00:00Z")
    naive = cs._to_local("2026-05-04T08:00:00")
    assert z == naive == datetime(2026, 5, 4, 8, 0, tzinfo=timezone.utc)
    assert z.tzinfo is not None


def make_service(response=None, error=None):
    service = cs.CalendarService.__new__(cs.CalendarService)
    api = MagicMock()
    request = api.events.return_value.list.return_value
    if error is not None:
        request.execute.side_effect = error
    else:
        request.execute.return_value = response or {}
    service._service = api
    return service, api


def test_upcoming_events_ordena_y_filtra():
    service, api = make_service(
        {
            "items": [
                item(id="tarde", start={"dateTime": "2026-05-04T12:00:00Z"}),
                item(id="todo-el-dia", start={"date": "2026-05-04"}),
                item(id="pronto", start={"dateTime": "2026-05-04T09:00:00Z"}),
            ]
        }
    )
    events = service.upcoming_events(hours=6, max_results=10)
    assert [e.id for e in events] == ["pronto", "tarde"]

    kwargs = api.events.return_value.list.call_args.kwargs
    assert kwargs["calendarId"] == "primary"
    assert kwargs["singleEvents"] is True
    assert kwargs["orderBy"] == "startTime"
    assert kwargs["maxResults"] == 10
    start = datetime.fromisoformat(kwargs["timeMin"])
    end = datetime.fromisoformat(kwargs["timeMax"])
    assert end - start == timedelta(hours=6)
    assert abs(start - datetime.now(timezone.utc)) < timedelta(seconds=5)


def test_upcoming_events_por_defecto_24h_y_100():
    service, api = make_service({"items": []})
    assert service.upcoming_events() == []
    kwargs = api.events.return_value.list.call_args.kwargs
    assert kwargs["maxResults"] == 100
    span = datetime.fromisoformat(kwargs["timeMax"]) - datetime.fromisoformat(kwargs["timeMin"])
    assert span == timedelta(hours=24)


def test_upcoming_events_sin_items():
    service, _ = make_service({})
    assert service.upcoming_events() == []


def test_upcoming_events_error_de_api():
    response = MagicMock(status=403, reason="Forbidden")
    service, _ = make_service(error=HttpError(response, b"{}"))
    with pytest.raises(RuntimeError, match="Google Calendar respondió un error"):
        service.upcoming_events()


def test_calendar_service_construye_cliente_con_timeout(monkeypatch):
    built = {}

    def fake_build(name, version, http, cache_discovery):
        built.update(name=name, version=version, http=http, cache=cache_discovery)
        return "api"

    monkeypatch.setattr(cs, "build", fake_build)
    creds = MagicMock()
    service = cs.CalendarService(credentials=creds)
    assert service._service == "api"
    assert built["http"].credentials is creds
    assert (built["name"], built["version"], built["cache"]) == ("calendar", "v3", False)
    assert built["http"].http.timeout == 30


class FakeAuth:
    def __init__(self, creds):
        self.creds = creds

    def get_credentials(self):
        return self.creds


def test_event_fetcher_sin_sesion_devuelve_lista_vacia():
    assert cs.EventFetcher(FakeAuth(None))() == []


def test_event_fetcher_reutiliza_cliente_y_lo_renueva_al_cambiar_credenciales(monkeypatch):
    created = []

    class FakeService:
        def __init__(self, creds):
            created.append(creds)

        def upcoming_events(self, hours):
            return [f"evento-{hours}"]

    monkeypatch.setattr(cs, "CalendarService", FakeService)
    first, second = object(), object()
    auth = FakeAuth(first)
    fetcher = cs.EventFetcher(auth)

    assert fetcher(hours=12) == ["evento-12"]
    assert fetcher() == ["evento-24"]
    assert created == [first]

    auth.creds = second
    fetcher()
    assert created == [first, second]

    auth.creds = None
    assert fetcher() == []
    assert fetcher._service is None
    auth.creds = second
    fetcher()
    assert created == [first, second, second]
