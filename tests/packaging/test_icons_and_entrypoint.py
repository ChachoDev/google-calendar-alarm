from __future__ import annotations

import os
import runpy
import struct
import sys
from pathlib import Path

import make_icons  # packaging/make_icons.py
import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_ico_valido(tmp_path):
    pngs = {16: b"a" * 10, 32: b"b" * 20, 256: b"c" * 30}
    path = tmp_path / "x.ico"
    make_icons.write_ico(path, pngs)
    data = path.read_bytes()
    reserved, kind, count = struct.unpack("<HHH", data[:6])
    assert (reserved, kind, count) == (0, 1, 3)
    entries = [struct.unpack("<BBBBHHII", data[6 + 16 * i : 22 + 16 * i]) for i in range(3)]
    assert [e[0] for e in entries] == [16, 32, 0]  # 256 se codifica como 0
    for (_w, _h, _c, _r, _p, _bpp, size, offset), payload in zip(
        entries, pngs.values(), strict=True
    ):
        assert data[offset : offset + size] == payload


def test_icns_valido(tmp_path):
    pngs = {16: b"a" * 10, 1024: b"z" * 40, 48: b"ignorado"}
    path = tmp_path / "x.icns"
    make_icons.write_icns(path, pngs)
    data = path.read_bytes()
    assert data[:4] == b"icns"
    assert struct.unpack(">I", data[4:8])[0] == len(data)
    assert data[8:12] == b"icp4"
    assert struct.unpack(">I", data[12:16])[0] == 18
    assert b"ic10" in data
    assert b"ignorado" not in data  # 48 px no tiene tipo ICNS


def test_genera_los_tres_iconos(tmp_path, monkeypatch, qapp):
    monkeypatch.setattr(sys, "argv", ["make_icons.py", "--out", str(tmp_path)])
    assert make_icons.main() == 0
    for name in ("CalendarAlarm.png", "CalendarAlarm.ico", "CalendarAlarm.icns"):
        assert (tmp_path / name).stat().st_size > 1000
    assert (tmp_path / "CalendarAlarm.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_icon_tamano(qapp):
    image = make_icons.render_icon(128)
    assert (image.width(), image.height()) == (128, 128)


@pytest.fixture
def entrypoint_env(monkeypatch):
    import calendar_alarm.__main__ as main_module

    calls = []
    monkeypatch.setattr(main_module, "main", lambda: calls.append(True) or 0)
    monkeypatch.delenv("PYGAME_HIDE_SUPPORT_PROMPT", raising=False)
    return calls


def test_entrypoint_sin_consola_redirige_salidas(monkeypatch, entrypoint_env):
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    module = runpy.run_path(str(ROOT / "packaging" / "entrypoint.py"), run_name="entry")
    assert sys.stdout is not None and sys.stderr is not None
    print("no falla")
    sys.stdout.close()
    sys.stderr.close()
    assert os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] == "1"
    assert callable(module["main"])
    assert entrypoint_env == []  # no arranca la app si no es __main__


def test_entrypoint_conserva_salidas_existentes(entrypoint_env):
    before = sys.stdout
    runpy.run_path(str(ROOT / "packaging" / "entrypoint.py"), run_name="entry")
    assert sys.stdout is before


def test_entrypoint_arranca_la_app(entrypoint_env):
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(str(ROOT / "packaging" / "entrypoint.py"), run_name="__main__")
    assert exit_info.value.code == 0
    assert entrypoint_env == [True]


def test_entrypoint_en_windows_fija_app_user_model_id(monkeypatch, entrypoint_env):
    import ctypes
    from unittest.mock import MagicMock

    windll = MagicMock()
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(ctypes, "windll", windll, raising=False)
    runpy.run_path(str(ROOT / "packaging" / "entrypoint.py"), run_name="entry")
    windll.shell32.SetCurrentProcessExplicitAppUserModelID.assert_called_once_with(
        "CalendarAlarm.CalendarAlarm"
    )
