"""Configuración común: entorno aislado, Qt sin pantalla y audio sin dispositivo."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Antes de importar Qt/pygame: sin pantalla ni tarjeta de sonido (CI, SSH...).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

ROOT = Path(__file__).resolve().parents[1]
for extra in (ROOT / "src", ROOT / "packaging"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import pytest

from calendar_alarm.config import CONFIG_DIR_ENV

GOOGLE_ENV = (
    "CALENDAR_ALARM_GOOGLE_CLIENT_FILE",
    "CALENDAR_ALARM_GOOGLE_CLIENT_ID",
    "CALENDAR_ALARM_GOOGLE_CLIENT_SECRET",
)


@pytest.fixture(autouse=True)
def isolated_environment(tmp_path, monkeypatch):
    """Cada test usa su propio directorio de configuración y ninguna credencial
    real de Google: nunca se toca la configuración ni el token del usuario."""
    config = tmp_path / "config"
    monkeypatch.setenv(CONFIG_DIR_ENV, str(config))
    for name in GOOGLE_ENV:
        monkeypatch.delenv(name, raising=False)
    return config


@pytest.fixture
def no_bundled_client(monkeypatch):
    """Simula una instalación sin google_client.json empaquetado."""
    from calendar_alarm import oauth_client

    monkeypatch.setattr(oauth_client, "CLIENT_ID", "")
    monkeypatch.setattr(oauth_client, "CLIENT_SECRET", "")
    monkeypatch.setattr(oauth_client, "asset_path", lambda _rel: Path("/nonexistent/x.json"))


@pytest.fixture
def dummy_client(monkeypatch, no_bundled_client):
    """Credenciales OAuth de mentira (nunca se llega a hablar con Google)."""
    monkeypatch.setenv("CALENDAR_ALARM_GOOGLE_CLIENT_ID", "dummy.apps.googleusercontent.com")
    monkeypatch.setenv("CALENDAR_ALARM_GOOGLE_CLIENT_SECRET", "dummy-secret")


@pytest.fixture
def make_event():
    """Fábrica de CalendarEvent con valores razonables por defecto."""
    from datetime import datetime, timedelta

    from calendar_alarm.models import CalendarEvent

    def factory(
        *,
        id: str = "evt-1",
        summary: str = "Reunión",
        description: str = "",
        location: str = "",
        start=None,
        end=None,
        minutes_from_now: float | None = None,
    ) -> CalendarEvent:
        now = datetime.now().astimezone()
        if start is None:
            start = now + timedelta(minutes=minutes_from_now if minutes_from_now is not None else 3)
        return CalendarEvent(
            id=id,
            summary=summary,
            description=description,
            location=location,
            start=start,
            end=end,
        )

    return factory
