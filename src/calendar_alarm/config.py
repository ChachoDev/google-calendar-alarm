from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from datetime import timedelta
from pathlib import Path

from platformdirs import user_config_path

APP_NAME = "CalendarAlarm"


def config_dir() -> Path:
    """Directorio de configuración según plataforma (~/.config, %APPDATA%, ~/Library...)."""
    path = user_config_path(APP_NAME, appauthor=False)
    path.mkdir(parents=True, exist_ok=True)
    return path


def asset_path(relative: str) -> Path:
    """Ruta a un recurso incluido con la aplicación (p. ej. ``assets/alarm.wav``).

    Funciona en desarrollo (paquete instalado) y en el ejecutable congelado
    con PyInstaller (los datos se extraen en ``sys._MEIPASS``).
    """
    from importlib.resources import files

    try:
        candidate = files("calendar_alarm").joinpath(relative)
        if candidate.is_file():
            return Path(str(candidate))
    except (ImportError, ModuleNotFoundError, TypeError):
        pass

    import sys

    base = getattr(sys, "_MEIPASS", None)
    if base:
        frozen = Path(base) / "calendar_alarm" / relative
        if frozen.is_file():
            return frozen

    return Path(__file__).resolve().parent / relative


def default_sound_path() -> str:
    """Ruta al sonido de alarma incluido con la aplicación."""
    return str(asset_path("assets/alarm.wav"))


@dataclass
class Config:
    # Margen de aviso por defecto: 5 minutos antes del evento
    warn_hours: int = 0
    warn_minutes: int = 5
    # Ruta al sonido personalizado; vacío => sonido por defecto incluido
    sound_path: str = ""
    # Segundos entre consultas a la API de Google Calendar
    poll_interval: int = 60

    @property
    def warn_delta(self) -> timedelta:
        return timedelta(hours=int(self.warn_hours), minutes=int(self.warn_minutes))

    @property
    def resolved_sound_path(self) -> str:
        return self.sound_path or default_sound_path()

    @property
    def warn_label(self) -> str:
        parts: list[str] = []
        if self.warn_hours:
            parts.append(f"{self.warn_hours} h")
        if self.warn_minutes or not parts:
            parts.append(f"{self.warn_minutes} min")
        return " ".join(parts)


def _config_file() -> Path:
    return config_dir() / "config.json"


def load_config() -> Config:
    path = _config_file()
    if not path.exists():
        return Config()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return Config()
    known = {f.name for f in fields(Config)}
    return Config(**{k: v for k, v in raw.items() if k in known})


def save_config(config: Config) -> None:
    path = _config_file()
    try:
        path.write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")
    except OSError:
        pass
