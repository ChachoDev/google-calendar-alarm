from __future__ import annotations

from datetime import datetime, timedelta, timezone

from calendar_alarm.models import CalendarEvent

TZ = timezone(timedelta(hours=1))


def event(start: datetime, end: datetime | None = None) -> CalendarEvent:
    return CalendarEvent(id="1", summary="S", description="", location="", start=start, end=end)


def test_formatos_de_hora_y_fecha():
    e = event(datetime(2026, 3, 7, 9, 5, tzinfo=TZ), datetime(2026, 3, 7, 10, 30, tzinfo=TZ))
    assert e.start_str == "09:05"
    assert e.end_str == "10:30"
    assert e.date_str == "07/03/2026"


def test_sin_fin_muestra_guiones():
    e = event(datetime(2026, 3, 7, 9, 5, tzinfo=TZ))
    assert e.end_str == "--:--"
    assert e.schedule_str() == "07/03/2026 · 09:05"


def test_horario_en_el_mismo_dia():
    e = event(datetime(2026, 3, 7, 9, 0, tzinfo=TZ), datetime(2026, 3, 7, 10, 0, tzinfo=TZ))
    assert e.schedule_str() == "07/03/2026 · 09:00 – 10:00"


def test_horario_que_acaba_otro_dia_muestra_fecha_final():
    e = event(datetime(2026, 3, 7, 23, 0, tzinfo=TZ), datetime(2026, 3, 8, 1, 15, tzinfo=TZ))
    assert e.schedule_str() == "07/03/2026 · 23:00 – 08/03/2026 01:15"


def test_es_inmutable():
    e = event(datetime(2026, 3, 7, 9, 0, tzinfo=TZ))
    try:
        e.summary = "otro"  # type: ignore[misc]
    except AttributeError:
        return
    raise AssertionError("CalendarEvent debería ser inmutable")
