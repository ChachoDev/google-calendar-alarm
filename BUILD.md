# Crear el ejecutable de Calendar Alarm

Calendar Alarm se empaqueta con **PyInstaller** en un entorno **aislado**. El
script `packaging/build.py` detecta el sistema operativo donde se ejecuta y
genera el artefacto nativo correspondiente, **autocontenido**: lleva dentro el
intérprete de Python, todas las dependencias (PySide6, pygame,
google-api-python-client…) y los recursos (sonido de alarma e iconos).

| Sistema donde ejecutas el script | Artefacto generado                            |
|----------------------------------|-----------------------------------------------|
| **Windows**                      | `dist/CalendarAlarm.exe` (un único `.exe`)    |
| **Linux**                        | `dist/calendar-alarm` (binario único)         |
| **macOS**                        | `dist/Calendar Alarm.app` + `dist/CalendarAlarm.dmg` |

> El ejecutable **no requiere Python instalado** en el equipo de destino.
> No se puede compilar para Windows desde Linux ni para macOS desde Windows:
> cada artefacto debe generarse en su propio sistema (o con el workflow de CI
> incluido, que compila los tres a la vez).

---

## 1. Dependencias necesarias

### Dependencias de empaquetado (las instala el script solo)

**No hay que añadir nada a `pyproject.toml` ni al entorno de desarrollo.** El
script crea un entorno virtual aparte en `build/build-env/` (con `uv` o, si no
está instalado, con `venv` + `pip`) e instala allí, únicamente para el
empaquetado:

- `pyinstaller>=6.11`
- `pyinstaller-hooks-contrib>=2024.8`
- el propio proyecto y sus dependencias de ejecución (desde `pyproject.toml`)

Así tu `.venv` de desarrollo queda intacto: no se modifican versiones ni se
instalan paquetes nuevos en él.

### Requisitos en el sistema

Hay dos modos; el script elige solo:

1. **Con uv (recomendado)**: crea el entorno aislado y **descarga Python 3.13**
   si no lo tienes. No necesitas Python instalado.
   - Linux/macOS: `curl -LsSf https://astral.sh/uv/install.sh | sh`
   - Windows (PowerShell): `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
2. **Sin uv**: usa un **Python 3.11–3.13 del sistema** con `venv` y `pip`.
   Si solo tienes Python 3.14 o superior, instala uv (o un Python 3.13).
- **Linux**: bibliotecas gráficas normales de escritorio (Qt). En Debian/Ubuntu:

  ```bash
  sudo apt install libegl1 libgl1 libxkbcommon-x11-0 libxcb-cursor0 \
      libxcb-icccm4 libxcb-keysyms1 libxcb-shape0 libdbus-1-3
  ```

  En Arch/Manjaro no suele faltar nada; si acaso `pacman -S libxkbcommon
  xcb-util-cursor mesa`.
- **macOS**: herramientas de línea de comandos de Xcode (`xcode-select --install`)
  para `hdiutil` y el firmado ad-hoc. No se necesita cuenta de desarrollador
  para uso propio.
- **Windows**: con uv, nada extra; sin uv, un Python 3.11–3.13 en el `PATH`.

---

## 2. Cómo ejecutar el script en cada sistema

Todos los comandos se lanzan **desde la raíz del proyecto**.

> Con uv se usa `uv run --no-project` para que el script corra con un Python
> temporal y **no** sincronice ni altere el `.venv` del proyecto. Sin uv, el
> script se ejecuta directamente con tu Python 3.11–3.13.

### Linux

```bash
uv run --no-project python packaging/build.py   # con uv (recomendado)
python3 packaging/build.py                      # sin uv (Python 3.11–3.13)
./dist/calendar-alarm
```

### Windows (PowerShell o CMD)

```powershell
uv run --no-project python packaging\build.py   # con uv (recomendado)
python packaging\build.py                       # sin uv (Python 3.11–3.13)
.\dist\CalendarAlarm.exe
```

La primera vez, SmartScreen puede avisar de que el archivo no está firmado:
pulsa **Más información → Ejecutar de todas formas** (el binario es tuyo).

### macOS

```bash
uv run --no-project python packaging/build.py   # con uv (recomendado)
python3 packaging/build.py                      # sin uv (Python 3.11–3.13)
open "dist/Calendar Alarm.app"
# o el instalador:
open dist/CalendarAlarm.dmg
```

La primera vez macOS puede bloquear la app descargada de internet. Como no está
firmada con un certificado de Apple, ábrela con **clic derecho → Abrir**, o
ejecuta:

```bash
xattr -dr com.apple.quarantine "dist/Calendar Alarm.app"
```

### Opciones del script

```bash
python packaging/build.py --help
```

| Opción            | Efecto                                                        |
|-------------------|---------------------------------------------------------------|
| `--no-clean`      | Reutiliza `build/` y `dist/` (por defecto se limpian)         |
| `--no-dmg`        | macOS: genera solo la `.app`, sin `.dmg`                      |
| `--python 3.12`   | Versión de Python del entorno de build (por defecto `3.13`)   |

---

## 3. Qué hace el script paso a paso

1. Detecta el sistema operativo (`win32`, `darwin` o Linux).
2. Limpia `build/` y `dist/` (salvo `--no-clean`).
3. Crea `build/build-env/` con `uv venv --python 3.13` o, si no hay uv, con
   `python -m venv` usando un Python 3.11–3.13 del sistema.
4. Instala el proyecto limpio y PyInstaller **solo ahí** (`uv pip install` o
   `pip install`).
5. Genera los iconos de la app (PNG, ICO e ICNS) en `build/icons/` mediante
   `packaging/make_icons.py`, dibujados con el mismo diseño de la campana.
6. Ejecuta PyInstaller sobre `packaging/entrypoint.py` incluyendo el paquete
   `calendar_alarm` completo (con `assets/alarm.wav`) y los imports dinámicos
   de Google que PyInstaller no detecta solo.
7. En macOS crea además el `.dmg` con `hdiutil`.
8. Verifica que el artefacto existe y muestra su ruta y tamaño.

Resultado esperado (ejemplo en Linux):

```
==> Empaquetado terminado
    - /home/tu-usuario/alarm/dist/calendar-alarm  (… MiB)

La aplicación ya se puede distribuir tal cual (no requiere Python).
```

---

## 4. Cómo arrancar la aplicación

### En desarrollo (con Python y uv)

```bash
uv sync          # solo la primera vez
uv run calendar-alarm
```

### Con el ejecutable ya empaquetado

- **Windows**: doble clic en `dist\CalendarAlarm.exe`. También puedes crear un
  acceso directo y copiarlo al menú Inicio.
- **Linux**: `./dist/calendar-alarm`. Para añadirlo al menú de aplicaciones,
  usa el bloque de comandos de más abajo.
- **macOS**: doble clic en `dist/Calendar Alarm.app`, o arrástrala a
  **Aplicaciones** desde el `.dmg`.

Para integrar la versión de Linux en el menú de aplicaciones:

```bash
mkdir -p ~/.local/bin ~/.local/share/applications \
    ~/.local/share/icons/hicolor/1024x1024/apps
cp dist/calendar-alarm ~/.local/bin/
cp build/icons/CalendarAlarm.png \
    ~/.local/share/icons/hicolor/1024x1024/apps/calendar-alarm.png
cat > ~/.local/share/applications/calendar-alarm.desktop <<EOF
[Desktop Entry]
Type=Application
Name=Calendar Alarm
Comment=Alarmas de Google Calendar
Exec=$HOME/.local/bin/calendar-alarm
Icon=calendar-alarm
Terminal=false
Categories=Utility;Calendar;
EOF
update-desktop-database ~/.local/share/applications 2>/dev/null || true
```

El heredoc sin comillas expande `$HOME`, así que `Exec` queda con la ruta
absoluta que exige el formato `.desktop`.

El primer arranque abre la configuración: elige tu `client_secret.json`,
pulsa **Conectar con Google** y ajusta el margen de aviso. Los datos de sesión
se guardan en el directorio de configuración del sistema
(`~/.config/CalendarAlarm/`, `%APPDATA%\CalendarAlarm\` o
`~/Library/Application Support/CalendarAlarm/`).

---

## 5. Compilar los tres sistemas con GitHub Actions

El repositorio incluye `.github/workflows/build.yml`: al subir un tag `v*` (o
lanzarlo a mano desde **Actions → Build executables → Run workflow**) compila en
Ubuntu, Windows y macOS y publica los artefactos descargables:

1. Sube el proyecto a GitHub (ver sección 7).
2. **Actions → Build executables → Run workflow**.
3. Al terminar, descarga los artefactos de la ejecución
   (`calendar-alarm-linux`, `-windows`, `-macos`).
4. Si haces `git push origin v1.0.0`, además se crea una **Release** con los
   binarios adjuntos.

---

## 6. Notas importantes de distribución

- **Arquitectura**: el binario es nativo de la máquina donde se compila
  (`x86_64` o `arm64`). Para distribuir a equipos ARM (p. ej. Mac con Apple
  Silicon) compílalo en un equipo ARM o con el runner `macos-14`+ del CI.
- **Linux y glibc**: un binario compilado en una distribución nueva puede no
  arrancar en otra más antigua. Para máxima compatibilidad, compílalo en la
  versión de Linux más antigua que vayas a soportar (el workflow usa el runner
  `ubuntu-22.04`).
- **Firma de código**: los artefactos no están firmados.
  - Windows: SmartScreen mostrará un aviso la primera vez; se elimina con un
    certificado de firma de código (de pago).
  - macOS: Gatekeeper requiere **clic derecho → Abrir** o quitar la cuarentena
    (`xattr -dr com.apple.quarantine`, ver arriba). Para distribución pública
    hace falta una cuenta de Apple Developer y `codesign` + `notarytool`.
- **Tamaño**: los binarios rondan 80–150 MiB porque incluyen Qt completo,
  Python y todas las dependencias. Es lo esperado en un ejecutable
  autocontenido.
- **Antivirus**: algunos antivirus marcan falsos positivos con ejecutables
  PyInstaller recién compilados; suele resolverse firmándolos.

---

## 7. Subir el proyecto a git

```bash
cd /home/victor/alarm
git init
git add .
git commit -m "Calendar Alarm: aplicación y empaquetado multiplataforma"
git branch -M main
git remote add origin https://github.com/TU-USUARIO/calendar-alarm.git
git push -u origin main
```

El `.gitignore` ya excluye `.venv/`, `build/`, `dist/`, cachés y las
credenciales (`client_secret*.json`, `token.json`). **Nunca subas esos dos
archivos.**

Para publicar una versión con binarios:

```bash
git tag v1.0.0
git push origin v1.0.0
```

---

## 8. Solución de problemas al empaquetar

| Síntoma | Causa / solución |
|---|---|
| `No se encontró 'uv' ni un Python 3.13` | Instala uv (recomendado) o un Python 3.11–3.13 con `venv` y `pip`. |
| PyInstaller no encuentra `PySide6` | Borra `build/` y vuelve a ejecutar sin `--no-clean`. |
| El `.exe` se abre y se cierra al instante | Compílalo con consola para ver el error: añade temporalmente `--console` a la orden de PyInstaller en `packaging/build.py`. |
| La alarma no suena en el ejecutable | Comprueba que `calendar_alarm/assets/alarm.wav` está en el wheel; el script usa `--collect-data calendar_alarm`. |
| macOS: «app dañada» | Es la cuarentena de Gatekeeper: `xattr -dr com.apple.quarantine "dist/Calendar Alarm.app"`. |
| Linux: falta `libEGL.so.1` | Instala las dependencias gráficas del apartado 1. |
| Icono vacío en Windows | Vuelve a generar iconos: `rm -rf build && python packaging/build.py`. |
