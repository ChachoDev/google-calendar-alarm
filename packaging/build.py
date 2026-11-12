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


def warn_missing_google_client() -> None:
    """Avisa si el ejecutable se va a compilar sin credenciales de Google."""
    client_file = ROOT / "src" / "calendar_alarm" / "assets" / "google_client.json"
    if client_file.is_file():
        return
    print(
        "\nADVERTENCIA: no existe src/calendar_alarm/assets/google_client.json.\n"
        "  El ejecutable se generará, pero el botón «Conectar con Google» no\n"
        "  podrá abrir el navegador. Consulta «Cliente OAuth de Google» en BUILD.md.",
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
    warn_missing_google_client()
    python = prepare_build_environment(args.python)
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
