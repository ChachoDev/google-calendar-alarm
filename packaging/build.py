#!/usr/bin/env python3
"""Empaqueta Calendar Alarm de forma nativa para el sistema operativo actual.

Genera, según la plataforma en la que se ejecute:

    Windows  ->  dist/CalendarAlarm.exe        (un único ejecutable autocontenido)
    Linux    ->  dist/calendar-alarm           (binario autocontenido)
    macOS    ->  dist/Calendar Alarm.app       (bundle) + dist/CalendarAlarm.dmg

Incluye el intérprete de Python, todas las dependencias (PySide6, pygame,
google-api-python-client...) y los recursos (sonido de alarma, iconos).

El entorno de desarrollo NO se toca: se crea un entorno virtual de empaquetado
aislado en build/build-env, se instala allí el proyecto limpio y PyInstaller, y
se construye desde ese entorno.

Uso (desde la raíz del proyecto):

    python3 packaging/build.py                     # Python 3.11-3.13 del sistema
    uv run --no-project python packaging/build.py  # alternativa si no hay Python

No requiere uv: se usa un Python 3.11–3.13 del sistema (venv + pip). Si no hay
ninguno instalado, el script recurre a uv cuando está disponible para crear el
entorno de build con la versión indicada.

Opciones:

    --no-clean          No borrar build/ y dist/ antes de empezar
    --no-dmg            (macOS) No crear el .dmg, solo la .app
    --python VERSION    Versión de Python para el entorno de build (def. 3.13)
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

ROOT = Path(__file__).resolve().parents[1]
BUILD_DIR = ROOT / "build"
BUILD_ENV = BUILD_DIR / "build-env"
PYINSTALLER_WORK = BUILD_DIR / "pyinstaller"
ICONS_DIR = BUILD_DIR / "icons"
DIST_DIR = ROOT / "dist"

APP_NAME_WINDOWS = "CalendarAlarm"
APP_NAME_LINUX = "calendar-alarm"
APP_NAME_MACOS = "Calendar Alarm"
BUNDLE_ID = "com.calendaralarm.app"

PACKAGING_REQUIREMENTS = [
    "pyinstaller>=6.11",
    "pyinstaller-hooks-contrib>=2024.8",
]

# Archivo local con las credenciales de Google. Está en .gitignore y el script
# lo lee para inyectarlo solo en el binario.
LOCAL_CLIENT_FILE = ROOT / "client_secret.json"

# Imports dinámicos que PyInstaller no puede descubrir por sí solo.
HIDDEN_IMPORTS = [
    "googleapiclient.discovery_cache",
    "googleapiclient.discovery_cache.documents",
    "google_auth_httplib2",
]


def log(message: str) -> None:
    print(f"\n==> {message}", flush=True)


def fail(message: str) -> NoReturn:
    print(f"\nERROR: {message}", file=sys.stderr, flush=True)
    raise SystemExit(1)


def run(command: list[object], *, env: dict[str, str] | None = None) -> None:
    printable = " ".join(str(part) for part in command)
    print(f"    $ {printable}", flush=True)
    subprocess.run([str(part) for part in command], cwd=ROOT, check=True, env=env)


def find_uv() -> str | None:
    """Devuelve la ruta de uv, o None para usar venv + pip del sistema."""
    return shutil.which("uv")


def _python_version(executable: str) -> str | None:
    try:
        result = subprocess.run(
            [
                executable,
                "-c",
                "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
    except OSError:
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def find_system_python(python_version: str) -> str | None:
    """Busca un intérprete compatible que pueda crear entornos con pip."""
    candidates = [f"python{python_version}", "python3", "python", sys.executable]
    checked: set[str] = set()
    for name in candidates:
        executable = shutil.which(name) or (name if os.path.isabs(name) else None)
        if executable is None or executable in checked:
            continue
        checked.add(executable)
        if _python_version(executable) != python_version:
            continue
        probe = subprocess.run(
            [executable, "-c", "import venv, ensurepip"],
            capture_output=True,
            check=False,
        )
        if probe.returncode == 0:
            # Se resuelven los symlinks: si `python3` apunta a otra ruta, el
            # venv debe crearse desde la instalación real (su `home`).
            return os.path.realpath(executable)
    return None


def venv_python() -> Path:
    if os.name == "nt":
        return BUILD_ENV / "Scripts" / "python.exe"
    return BUILD_ENV / "bin" / "python"


def clean(previous: bool) -> None:
    if not previous:
        return
    log("Limpiando artefactos anteriores (build/ y dist/)")
    for path in (BUILD_ENV, PYINSTALLER_WORK, ICONS_DIR, DIST_DIR):
        shutil.rmtree(path, ignore_errors=True)


def _installed_assets_dir(python: Path) -> Path | None:
    """Directorio de recursos del paquete instalado en el entorno de build."""
    probe = subprocess.run(
        [
            python,
            "-c",
            (
                "import calendar_alarm, pathlib; "
                "print(pathlib.Path(calendar_alarm.__file__).parent / 'assets')"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode != 0:
        return None
    return Path(probe.stdout.strip())


def _read_credentials_file(path: Path) -> dict[str, object] | None:
    """Lee un JSON de credenciales (formato ``installed`` o ``web``)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    section = data.get("installed") or data.get("web")
    if not isinstance(section, dict) or not section.get("client_id"):
        return None
    return {"installed": section}


def prepare_google_client(python: Path) -> None:
    """Inyecta las credenciales OAuth solo en el binario, nunca en el repo.

    Orden de búsqueda:

    1. ``CALENDAR_ALARM_GOOGLE_CLIENT_ID`` + ``_SECRET`` del entorno.
    2. Archivo indicado en ``CALENDAR_ALARM_GOOGLE_CLIENT_FILE``.
    3. ``client_secret.json`` en la raíz del proyecto (en .gitignore).
    4. ``src/calendar_alarm/assets/google_client.json`` (también ignorado).

    Se copian al paquete instalado (``.../site-packages/calendar_alarm/assets``)
    para que PyInstaller las empaquete. El código fuente y git quedan limpios.
    """
    client_id = os.environ.get("CALENDAR_ALARM_GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("CALENDAR_ALARM_GOOGLE_CLIENT_SECRET", "").strip()

    assets = _installed_assets_dir(python)
    if assets is None:
        fail("No se pudo localizar el paquete calendar_alarm en el entorno de build.")
    assets.mkdir(parents=True, exist_ok=True)
    installed_client = assets / "google_client.json"
    # Evita reutilizar credenciales inyectadas en una build anterior
    # (importante con --no-clean).
    installed_client.unlink(missing_ok=True)

    if client_id and client_secret:
        config = {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }
        installed_client.write_text(json.dumps(config, indent=2), encoding="utf-8")
        print("    Credenciales OAuth inyectadas desde el entorno", flush=True)
        return

    env_file = os.environ.get("CALENDAR_ALARM_GOOGLE_CLIENT_FILE", "").strip()
    candidates = [Path(env_file).expanduser()] if env_file else []
    candidates.append(LOCAL_CLIENT_FILE)
    candidates.append(ROOT / "src" / "calendar_alarm" / "assets" / "google_client.json")

    for candidate in candidates:
        config = _read_credentials_file(candidate)
        if config is None:
            continue
        installed_client.write_text(json.dumps(config, indent=2), encoding="utf-8")
        print(f"    Credenciales OAuth tomadas de {candidate}", flush=True)
        return

    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("CALENDAR_ALARM_GOOGLE")
    }
    probe = subprocess.run(
        [
            python,
            "-c",
            "from calendar_alarm.oauth_client import is_configured; print(is_configured())",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    if probe.stdout.strip() == "True":
        return
    print(
        "\nADVERTENCIA: la app se compilará sin credenciales de Google.\n"
        "  El botón «Conectar con Google» no podrá abrir el navegador.\n"
        "  Define CALENDAR_ALARM_GOOGLE_CLIENT_ID y\n"
        "  CALENDAR_ALARM_GOOGLE_CLIENT_SECRET, o rellena las constantes de\n"
        "  src/calendar_alarm/oauth_client.py (ver BUILD.md).",
        flush=True,
    )


def prepare_build_environment(python_version: str) -> Path:
    """Crea un entorno aislado con el proyecto limpio + PyInstaller.

    Preferencia: Python del sistema (venv + pip). Si no hay un 3.11–3.13
    instalado, se usa uv como respaldo para crear el entorno.
    """
    log(f"Creando entorno de empaquetado aislado (Python {python_version})")
    python = venv_python()
    base = find_system_python(python_version)

    if base is not None:
        print(f"    Usando Python del sistema: {base} (venv + pip)", flush=True)
        run([base, "-m", "venv", "--clear", BUILD_ENV])
        install = [python, "-m", "pip", "install", "--quiet"]
    else:
        uv = find_uv()
        if uv is None:
            fail(
                f"No se encontró un Python {python_version} con venv/pip ni 'uv'.\n"
                f"  Instala Python {python_version} y repite el comando, o instala uv\n"
                "  (https://docs.astral.sh/uv/), que puede descargar ese Python."
            )
        print(f"    Sin Python {python_version} en el sistema: usando uv", flush=True)
        run([uv, "venv", "--clear", "--python", python_version, BUILD_ENV])
        install = [uv, "pip", "install", "--python", python, "--quiet"]

    if not python.exists():
        fail(f"No se pudo crear el intérprete del entorno de build: {python}")

    log("Instalando el proyecto y sus dependencias en el entorno aislado")
    run([*install, "."])

    log("Instalando PyInstaller (solo en el entorno de build)")
    run([*install, *PACKAGING_REQUIREMENTS])
    return python


def generate_icons(python: Path) -> None:
    log("Generando iconos de la aplicación (PNG, ICO e ICNS)")
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    run(
        [python, ROOT / "packaging" / "make_icons.py", "--out", ICONS_DIR],
        env=env,
    )


def pyinstaller_command(python: Path) -> list[object]:
    command: list[object] = [
        python,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--log-level",
        "WARN",
        "--distpath",
        DIST_DIR,
        "--workpath",
        PYINSTALLER_WORK,
        "--specpath",
        PYINSTALLER_WORK,
        "--collect-data",
        "calendar_alarm",
    ]
    for hidden in HIDDEN_IMPORTS:
        command += ["--hidden-import", hidden]

    if sys.platform == "win32":
        command += [
            "--onefile",
            "--windowed",
            "--name",
            APP_NAME_WINDOWS,
            "--icon",
            ICONS_DIR / "CalendarAlarm.ico",
        ]
    elif sys.platform == "darwin":
        command += [
            "--windowed",
            "--name",
            APP_NAME_MACOS,
            "--icon",
            ICONS_DIR / "CalendarAlarm.icns",
            "--osx-bundle-identifier",
            BUNDLE_ID,
        ]
    else:
        command += [
            "--onefile",
            "--name",
            APP_NAME_LINUX,
            "--icon",
            ICONS_DIR / "CalendarAlarm.png",
        ]

    command.append(ROOT / "packaging" / "entrypoint.py")
    return command


def create_dmg() -> Path | None:
    app_path = DIST_DIR / f"{APP_NAME_MACOS}.app"
    if not app_path.exists() or shutil.which("hdiutil") is None:
        return None
    dmg_path = DIST_DIR / "CalendarAlarm.dmg"
    log("Creando imagen de disco (.dmg)")
    run(
        [
            "hdiutil",
            "create",
            "-volname",
            APP_NAME_MACOS,
            "-srcfolder",
            app_path,
            "-ov",
            "-format",
            "UDZO",
            dmg_path,
        ]
    )
    return dmg_path


def describe_outputs(dmg: Path | None) -> None:
    log("Empaquetado terminado")
    artifacts: list[Path] = []
    if sys.platform == "win32":
        artifacts.append(DIST_DIR / f"{APP_NAME_WINDOWS}.exe")
    elif sys.platform == "darwin":
        artifacts.append(DIST_DIR / f"{APP_NAME_MACOS}.app")
        if dmg is not None:
            artifacts.append(dmg)
    else:
        artifacts.append(DIST_DIR / APP_NAME_LINUX)

    for artifact in artifacts:
        if not artifact.exists():
            fail(f"No se generó el artefacto esperado: {artifact}")
        if artifact.is_dir():
            size = sum(p.stat().st_size for p in artifact.rglob("*") if p.is_file())
        else:
            size = artifact.stat().st_size
        print(f"    - {artifact}  ({size / (1024 * 1024):.1f} MiB)")

    print("\nLa aplicación ya se puede distribuir tal cual (no requiere Python).")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Genera el ejecutable nativo de Calendar Alarm para este sistema."
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="No borrar build/ y dist/ antes de construir",
    )
    parser.add_argument(
        "--no-dmg",
        action="store_true",
        help="(macOS) No crear el .dmg; solo la .app",
    )
    parser.add_argument(
        "--python",
        default="3.13",
        help="Versión de Python del entorno de build (por defecto 3.13)",
    )
    args = parser.parse_args()

    system = {"win32": "Windows", "darwin": "macOS"}.get(sys.platform, "Linux")
    log(f"Empaquetando Calendar Alarm para {system}")
    print(f"    Proyecto: {ROOT}")
    print(f"    Entorno de build aislado: {BUILD_ENV}")

    uv = find_uv()
    print(f"    uv: {uv or 'no encontrado (se usará venv + pip del sistema)'}")
    clean(not args.no_clean)
    python = prepare_build_environment(args.python)
    prepare_google_client(python)
    generate_icons(python)

    log("Construyendo el ejecutable con PyInstaller")
    run(pyinstaller_command(python))

    dmg = None
    if sys.platform == "darwin" and not args.no_dmg:
        dmg = create_dmg()

    describe_outputs(dmg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
