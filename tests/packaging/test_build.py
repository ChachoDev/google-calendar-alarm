"""Script de empaquetado: se comprueba la lógica de cada sistema sin compilar."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import build as b  # packaging/build.py (conftest añade packaging/ al path)


def flag_value(command, flag):
    return command[command.index(flag) + 1]


@pytest.mark.parametrize(
    ("platform", "name", "icon", "onefile", "windowed"),
    [
        ("win32", "CalendarAlarm", "CalendarAlarm.ico", True, True),
        ("darwin", "Calendar Alarm", "CalendarAlarm.icns", False, True),
        ("linux", "calendar-alarm", "CalendarAlarm.png", True, False),
    ],
)
def test_pyinstaller_por_sistema(monkeypatch, platform, name, icon, onefile, windowed):
    monkeypatch.setattr(b.sys, "platform", platform)
    command = b.pyinstaller_command(Path("/py"))
    assert command[:3] == [Path("/py"), "-m", "PyInstaller"]
    assert flag_value(command, "--name") == name
    assert Path(flag_value(command, "--icon")).name == icon
    assert ("--onefile" in command) is onefile
    assert ("--windowed" in command) is windowed
    assert ("--osx-bundle-identifier" in command) is (platform == "darwin")
    assert command[-1] == b.ROOT / "packaging" / "entrypoint.py"
    assert flag_value(command, "--collect-data") == "calendar_alarm"
    for hidden in b.HIDDEN_IMPORTS:
        assert hidden in command
    assert flag_value(command, "--distpath") == b.DIST_DIR


def test_artefactos_esperados_coinciden_con_el_nombre(monkeypatch, tmp_path):
    monkeypatch.setattr(b, "DIST_DIR", tmp_path)
    for platform, artifact in (
        ("win32", "CalendarAlarm.exe"),
        ("linux", "calendar-alarm"),
    ):
        monkeypatch.setattr(b.sys, "platform", platform)
        (tmp_path / artifact).write_bytes(b"x" * 10)
        b.describe_outputs(None)

    monkeypatch.setattr(b.sys, "platform", "darwin")
    app = tmp_path / "Calendar Alarm.app" / "Contents"
    app.mkdir(parents=True)
    (app / "bin").write_bytes(b"x")
    b.describe_outputs(None)


def test_falta_el_artefacto(monkeypatch, tmp_path):
    monkeypatch.setattr(b, "DIST_DIR", tmp_path)
    monkeypatch.setattr(b.sys, "platform", "linux")
    with pytest.raises(SystemExit):
        b.describe_outputs(None)


def test_entorno_pip_ignora_la_configuracion_del_usuario(monkeypatch):
    monkeypatch.setenv("PIP_USER", "1")
    monkeypatch.setenv("PIP_DEFAULT_TIMEOUT", "5")
    env = b.pip_environment()
    assert env["PIP_USER"] == "0"
    assert env["PIP_REQUIRE_VIRTUALENV"] == "0"
    assert env["PIP_DISABLE_PIP_VERSION_CHECK"] == "1"
    assert env["PIP_DEFAULT_TIMEOUT"] == "5"  # respeta lo que ya hubiera
    assert env["PIP_RETRIES"] == "5"


def test_venv_python_por_sistema(monkeypatch):
    monkeypatch.setattr(b.os, "name", "nt")
    assert b.venv_python().parts[-2:] == ("Scripts", "python.exe")
    monkeypatch.setattr(b.os, "name", "posix")
    assert b.venv_python().parts[-2:] == ("bin", "python")


def test_credenciales_formatos_validos_e_invalidos(tmp_path):
    good = tmp_path / "ok.json"
    good.write_text(json.dumps({"web": {"client_id": "x", "client_secret": "s"}}), "utf-8")
    assert b._read_credentials_file(good) == {"installed": {"client_id": "x", "client_secret": "s"}}
    for content in ("no json", "[]", '{"installed": {}}'):
        bad = tmp_path / "bad.json"
        bad.write_text(content, "utf-8")
        assert b._read_credentials_file(bad) is None
    assert b._read_credentials_file(tmp_path / "nada.json") is None


@pytest.fixture
def fake_assets(monkeypatch, tmp_path):
    assets = tmp_path / "site" / "calendar_alarm" / "assets"
    monkeypatch.setattr(b, "_installed_assets_dir", lambda _python: assets)
    monkeypatch.setattr(b, "LOCAL_CLIENT_FILE", tmp_path / "client_secret.json")
    monkeypatch.setattr(b, "ROOT", tmp_path)
    for name in (
        "CALENDAR_ALARM_GOOGLE_CLIENT_ID",
        "CALENDAR_ALARM_GOOGLE_CLIENT_SECRET",
        "CALENDAR_ALARM_GOOGLE_CLIENT_FILE",
    ):
        monkeypatch.delenv(name, raising=False)
    return assets


def test_inyecta_credenciales_desde_el_entorno(fake_assets, monkeypatch):
    monkeypatch.setenv("CALENDAR_ALARM_GOOGLE_CLIENT_ID", "env-id")
    monkeypatch.setenv("CALENDAR_ALARM_GOOGLE_CLIENT_SECRET", "env-secret")
    b.prepare_google_client(Path("/py"))
    data = json.loads((fake_assets / "google_client.json").read_text("utf-8"))
    assert data["installed"]["client_id"] == "env-id"
    assert data["installed"]["client_secret"] == "env-secret"


def test_inyecta_credenciales_desde_client_secret_json(fake_assets, tmp_path):
    (tmp_path / "client_secret.json").write_text(
        json.dumps({"installed": {"client_id": "local", "client_secret": "s"}}), "utf-8"
    )
    b.prepare_google_client(Path("/py"))
    data = json.loads((fake_assets / "google_client.json").read_text("utf-8"))
    assert data["installed"]["client_id"] == "local"


def test_archivo_de_entorno_tiene_prioridad(fake_assets, tmp_path, monkeypatch):
    (tmp_path / "client_secret.json").write_text(
        json.dumps({"installed": {"client_id": "local"}}), "utf-8"
    )
    other = tmp_path / "otro.json"
    other.write_text(json.dumps({"installed": {"client_id": "otro"}}), "utf-8")
    monkeypatch.setenv("CALENDAR_ALARM_GOOGLE_CLIENT_FILE", str(other))
    b.prepare_google_client(Path("/py"))
    data = json.loads((fake_assets / "google_client.json").read_text("utf-8"))
    assert data["installed"]["client_id"] == "otro"


def test_sin_credenciales_borra_las_de_builds_anteriores_y_avisa(fake_assets, monkeypatch, capsys):
    fake_assets.mkdir(parents=True)
    (fake_assets / "google_client.json").write_text("{}", "utf-8")
    monkeypatch.setattr(
        b.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, "False\n", "")
    )
    b.prepare_google_client(Path("/py"))
    assert not (fake_assets / "google_client.json").exists()
    assert "sin credenciales de Google" in capsys.readouterr().out


def test_paquete_no_instalado(monkeypatch):
    monkeypatch.setattr(b, "_installed_assets_dir", lambda _python: None)
    with pytest.raises(SystemExit):
        b.prepare_google_client(Path("/py"))


def test_python_del_sistema_por_version(monkeypatch):
    versions = {"/usr/bin/python3.13": "3.13", "/usr/bin/python3": "3.15"}
    monkeypatch.setattr(b.os, "name", "posix")
    monkeypatch.setattr(
        b.shutil, "which", lambda n: f"/usr/bin/{n}" if n in ("python3.13", "python3") else None
    )
    monkeypatch.setattr(b, "_python_version", lambda exe: versions.get(exe))
    monkeypatch.setattr(b.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0))
    monkeypatch.setattr(b.os.path, "realpath", lambda p: p)
    assert b.find_system_python("3.13") == "/usr/bin/python3.13"
    assert b.find_system_python("3.12") is None


def test_python_sin_venv_se_descarta(monkeypatch):
    monkeypatch.setattr(b.os, "name", "posix")
    monkeypatch.setattr(b.shutil, "which", lambda n: "/usr/bin/python3" if n == "python3" else None)
    monkeypatch.setattr(b, "_python_version", lambda exe: "3.13")
    monkeypatch.setattr(b.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 1))
    assert b.find_system_python("3.13") is None


def test_windows_usa_el_lanzador_py(monkeypatch):
    launcher_exe = r"C:\Python313\python.exe"
    monkeypatch.setattr(b.os, "name", "nt")
    monkeypatch.setattr(
        b, "_windows_launcher_python", lambda v: launcher_exe if v == "3.13" else None
    )
    monkeypatch.setattr(b.shutil, "which", lambda n: None)
    monkeypatch.setattr(b, "_python_version", lambda exe: "3.13" if exe == launcher_exe else None)
    monkeypatch.setattr(b.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0))
    monkeypatch.setattr(b.os.path, "realpath", lambda p: p)
    monkeypatch.setattr(b.os.path, "isabs", lambda p: p == launcher_exe)
    assert b.find_system_python("3.13") == launcher_exe


def test_lanzador_py(monkeypatch):
    monkeypatch.setattr(b.shutil, "which", lambda n: "C:/py.exe" if n == "py" else None)
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "C:/Python313/python.exe\n", "")

    monkeypatch.setattr(b.subprocess, "run", run)
    assert b._windows_launcher_python("3.13") == "C:/Python313/python.exe"
    assert calls[0][:2] == ["C:/py.exe", "-3.13"]

    monkeypatch.setattr(
        b.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 1, "", "")
    )
    assert b._windows_launcher_python("3.13") is None

    def timeout(*a, **k):
        raise subprocess.TimeoutExpired("py", 20)

    monkeypatch.setattr(b.subprocess, "run", timeout)
    assert b._windows_launcher_python("3.13") is None
    monkeypatch.setattr(b.shutil, "which", lambda n: None)
    assert b._windows_launcher_python("3.13") is None


def test_python_version_real():
    import sys

    assert b._python_version(sys.executable) == f"{sys.version_info[0]}.{sys.version_info[1]}"
    assert b._python_version("/no/existe/python") is None


class Recorder:
    def __init__(self, fail_times=0):
        self.commands = []
        self.envs = []
        self.fail_times = fail_times

    def __call__(self, command, *, env=None):
        self.commands.append([str(c) for c in command])
        self.envs.append(env)
        if self.fail_times:
            self.fail_times -= 1
            raise subprocess.CalledProcessError(1, command)


@pytest.fixture
def build_env(monkeypatch, tmp_path):
    env_dir = tmp_path / "build-env"
    python = env_dir / "bin" / "python"
    monkeypatch.setattr(b, "BUILD_ENV", env_dir)
    monkeypatch.setattr(b, "venv_python", lambda: python)
    recorder = Recorder()

    def run(command, *, env=None):
        recorder(command, env=env)
        python.parent.mkdir(parents=True, exist_ok=True)
        python.touch()

    monkeypatch.setattr(b, "run", run)
    return recorder


def test_entorno_con_uv(build_env, monkeypatch):
    monkeypatch.setattr(b, "find_system_python", lambda v: "/usr/bin/python3.13")
    monkeypatch.setattr(b, "find_uv", lambda: "/bin/uv")
    b.prepare_build_environment("3.13", use_pip=False)
    assert build_env.commands[0][:4] == ["/bin/uv", "venv", "--clear", "--python"]
    assert build_env.commands[0][4] == "/usr/bin/python3.13"
    assert build_env.commands[1][:3] == ["/bin/uv", "pip", "install"]
    assert build_env.commands[1][-1] == "."
    assert any("pyinstaller" in c for c in build_env.commands[2])
    assert build_env.envs[1] is None


def test_uv_descarga_python_si_no_hay(build_env, monkeypatch):
    monkeypatch.setattr(b, "find_system_python", lambda v: None)
    monkeypatch.setattr(b, "find_uv", lambda: "/bin/uv")
    b.prepare_build_environment("3.12", use_pip=False)
    assert build_env.commands[0][4] == "3.12"


def test_entorno_con_pip(build_env, monkeypatch):
    monkeypatch.setattr(b, "find_system_python", lambda v: "/usr/bin/python3.13")
    monkeypatch.setattr(b, "find_uv", lambda: "/bin/uv")
    b.prepare_build_environment("3.13", use_pip=True)
    assert build_env.commands[0] == [
        "/usr/bin/python3.13",
        "-m",
        "venv",
        "--clear",
        str(b.BUILD_ENV),
    ]
    assert build_env.commands[1][1:4] == ["-m", "pip", "install"]
    assert build_env.envs[1]["PIP_USER"] == "0"


def test_sin_python_ni_uv(build_env, monkeypatch):
    monkeypatch.setattr(b, "find_system_python", lambda v: None)
    monkeypatch.setattr(b, "find_uv", lambda: None)
    with pytest.raises(SystemExit):
        b.prepare_build_environment("3.13", use_pip=False)


def test_dmg_reintenta_si_hdiutil_esta_ocupado(monkeypatch, tmp_path):
    monkeypatch.setattr(b, "DIST_DIR", tmp_path)
    (tmp_path / "Calendar Alarm.app").mkdir()
    monkeypatch.setattr(b.shutil, "which", lambda n: "/usr/bin/hdiutil")
    monkeypatch.setattr(b.time, "sleep", lambda s: None)
    recorder = Recorder(fail_times=2)
    monkeypatch.setattr(b, "run", recorder)
    assert b.create_dmg() == tmp_path / "CalendarAlarm.dmg"
    assert len(recorder.commands) == 3
    assert recorder.commands[0][:2] == ["hdiutil", "create"]


def test_dmg_se_rinde_tras_varios_intentos(monkeypatch, tmp_path):
    monkeypatch.setattr(b, "DIST_DIR", tmp_path)
    (tmp_path / "Calendar Alarm.app").mkdir()
    monkeypatch.setattr(b.shutil, "which", lambda n: "/usr/bin/hdiutil")
    monkeypatch.setattr(b.time, "sleep", lambda s: None)
    recorder = Recorder(fail_times=99)
    monkeypatch.setattr(b, "run", recorder)
    with pytest.raises(subprocess.CalledProcessError):
        b.create_dmg()
    assert len(recorder.commands) == 4


def test_dmg_sin_app_o_sin_hdiutil(monkeypatch, tmp_path):
    monkeypatch.setattr(b, "DIST_DIR", tmp_path)
    assert b.create_dmg() is None
    (tmp_path / "Calendar Alarm.app").mkdir()
    monkeypatch.setattr(b.shutil, "which", lambda n: None)
    assert b.create_dmg() is None


def test_clean(monkeypatch, tmp_path):
    dirs = [tmp_path / n for n in ("env", "work", "icons", "dist")]
    for d in dirs:
        d.mkdir()
    monkeypatch.setattr(b, "BUILD_ENV", dirs[0])
    monkeypatch.setattr(b, "PYINSTALLER_WORK", dirs[1])
    monkeypatch.setattr(b, "ICONS_DIR", dirs[2])
    monkeypatch.setattr(b, "DIST_DIR", dirs[3])
    b.clean(False)
    assert all(d.exists() for d in dirs)
    b.clean(True)
    assert not any(d.exists() for d in dirs)


@pytest.mark.parametrize(
    ("platform", "args", "dmg_expected"),
    [("darwin", [], True), ("darwin", ["--no-dmg"], False), ("linux", [], False)],
)
def test_main_orquesta_los_pasos(monkeypatch, platform, args, dmg_expected):
    steps = []
    monkeypatch.setattr(b.sys, "platform", platform)
    monkeypatch.setattr(b.sys, "argv", ["build.py", "--no-clean", *args])
    monkeypatch.setattr(b, "clean", lambda previous: steps.append(("clean", previous)))
    monkeypatch.setattr(
        b,
        "prepare_build_environment",
        lambda v, use_pip: steps.append(("env", v, use_pip)) or Path("/py"),
    )
    monkeypatch.setattr(b, "prepare_google_client", lambda p: steps.append("google"))
    monkeypatch.setattr(b, "generate_icons", lambda p: steps.append("icons"))
    monkeypatch.setattr(b, "run", lambda c, env=None: steps.append("pyinstaller"))
    monkeypatch.setattr(b, "create_dmg", lambda: steps.append("dmg"))
    monkeypatch.setattr(b, "describe_outputs", lambda dmg: steps.append("outputs"))
    assert b.main() == 0
    expected = [("clean", False), ("env", "3.13", False), "google", "icons", "pyinstaller"]
    expected += ["dmg"] if dmg_expected else []
    assert steps == [*expected, "outputs"]
