from __future__ import annotations

import json
import wave
from datetime import timedelta
from pathlib import Path

import pytest

from calendar_alarm import config as cfg
from calendar_alarm.config import Config


def test_valores_por_defecto():
    c = Config()
    assert (c.warn_hours, c.warn_minutes) == (0, 5)
    assert c.sound_path == ""
    assert c.poll_interval == 60
    assert c.warn_delta == timedelta(minutes=5)


def test_warn_delta_combina_horas_y_minutos():
    assert Config(warn_hours=2, warn_minutes=15).warn_delta == timedelta(hours=2, minutes=15)


def test_warn_delta_acepta_texto_numerico():
    # Un config.json editado a mano puede traer cadenas.
    assert Config(warn_hours="1", warn_minutes="2").warn_delta == timedelta(hours=1, minutes=2)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("hours", "minutes", "label"),
    [
        (0, 5, "5 min"),
        (0, 0, "0 min"),
        (2, 0, "2 h"),
        (1, 30, "1 h 30 min"),
    ],
)
def test_warn_label(hours, minutes, label):
    assert Config(warn_hours=hours, warn_minutes=minutes).warn_label == label


def test_sonido_por_defecto_existe_y_es_wav_valido():
    path = Path(cfg.default_sound_path())
    assert path.is_file()
    assert path.name == "alarm.wav"
    with wave.open(str(path), "rb") as wav:
        assert wav.getnframes() > 0


def test_resolved_sound_path():
    assert Config().resolved_sound_path == cfg.default_sound_path()
    assert Config(sound_path="/tmp/x.mp3").resolved_sound_path == "/tmp/x.mp3"


def test_config_dir_respeta_variable_de_entorno(isolated_environment):
    path = cfg.config_dir()
    assert path == isolated_environment
    assert path.is_dir()


def test_config_dir_sin_variable_usa_platformdirs(monkeypatch, tmp_path):
    seen = {}

    def fake(name, appauthor):
        seen.update(name=name, appauthor=appauthor)
        return tmp_path / "anidado" / name

    monkeypatch.delenv(cfg.CONFIG_DIR_ENV)
    monkeypatch.setattr(cfg, "user_config_path", fake)
    assert cfg.config_dir() == tmp_path / "anidado" / "CalendarAlarm"
    assert (tmp_path / "anidado" / "CalendarAlarm").is_dir()  # crea los padres
    # appauthor=False: en Windows evita %APPDATA%\\CalendarAlarm\\CalendarAlarm
    assert seen == {"name": "CalendarAlarm", "appauthor": False}


def test_config_dir_crea_carpetas_intermedias(monkeypatch, tmp_path):
    target = tmp_path / "a" / "b" / "c"
    monkeypatch.setenv(cfg.CONFIG_DIR_ENV, str(target))
    assert cfg.config_dir() == target
    assert target.is_dir()


def test_guardar_y_cargar_ida_y_vuelta():
    # Ruta con caracteres no ASCII: en Windows detecta escrituras sin UTF-8.
    original = Config(
        warn_hours=1, warn_minutes=20, sound_path="/música/alarma ñ.ogg", poll_interval=120
    )
    cfg.save_config(original)
    assert cfg.load_config() == original


def test_cargar_sin_archivo_devuelve_por_defecto():
    assert cfg.load_config() == Config()


def test_cargar_json_corrupto_devuelve_por_defecto(isolated_environment):
    cfg.config_dir()
    (isolated_environment / "config.json").write_text("{ no es json", encoding="utf-8")
    assert cfg.load_config() == Config()


def test_cargar_ignora_claves_desconocidas(isolated_environment):
    cfg.config_dir()
    (isolated_environment / "config.json").write_text(
        json.dumps({"warn_minutes": 9, "clave_vieja": True}), encoding="utf-8"
    )
    loaded = cfg.load_config()
    assert loaded.warn_minutes == 9
    assert loaded.warn_hours == 0


def test_guardar_es_tolerante_a_errores_de_disco(monkeypatch):
    def boom(*_a, **_k):
        raise OSError("disco lleno")

    monkeypatch.setattr(Path, "write_text", boom)
    cfg.save_config(Config())  # no lanza


def test_save_escribe_json_legible(isolated_environment):
    cfg.save_config(Config(warn_minutes=7))
    assert [p.name for p in isolated_environment.iterdir()] == ["config.json"]
    text = (isolated_environment / "config.json").read_text(encoding="utf-8")
    assert json.loads(text) == {
        "warn_hours": 0,
        "warn_minutes": 7,
        "sound_path": "",
        "poll_interval": 60,
    }
    assert '\n  "warn_hours": 0' in text  # sangría de 2 espacios, editable a mano


def test_asset_path_en_ejecutable_congelado(monkeypatch, tmp_path):
    """Con PyInstaller los recursos están en sys._MEIPASS/calendar_alarm/..."""
    import importlib.resources
    import sys

    target = tmp_path / "calendar_alarm" / "assets" / "solo_congelado.bin"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"x")
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert cfg.asset_path("assets/solo_congelado.bin") == target
    assert importlib.resources  # import usado: el recurso no existe en el paquete


def test_asset_path_inexistente_devuelve_ruta_del_paquete():
    path = cfg.asset_path("assets/no_existe.bin")
    assert path == Path(cfg.__file__).resolve().parent / "assets/no_existe.bin"
