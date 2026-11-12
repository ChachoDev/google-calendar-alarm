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

### Resumen: generar y arrancar el ejecutable

Desde la raíz del proyecto (necesitas uv o un Python 3.11–3.13; detalles en el
apartado 2):

| Sistema | Generar el ejecutable | Arrancarlo |
|---|---|---|
| **Windows** (PowerShell/CMD) | `py packaging\build.py` | `.\dist\CalendarAlarm.exe` (o doble clic) |
| **Linux** | `python3 packaging/build.py` | `./dist/calendar-alarm` |
| **macOS** | `python3 packaging/build.py` | `open "dist/Calendar Alarm.app"` (o doble clic; para instalar, `open dist/CalendarAlarm.dmg` y arrastrar a Aplicaciones) |

> El ejecutable **no requiere Python instalado** en el equipo de destino.
> No se puede compilar para Windows desde Linux ni para macOS desde Windows:
> cada artefacto debe generarse en su propio sistema (o con el workflow de CI
> incluido, que compila los tres a la vez).

---

## 1. Dependencias necesarias

### Dependencias de empaquetado (las instala el script solo)

**No hay que añadir nada a `pyproject.toml` ni al entorno de desarrollo.** El
script crea un entorno virtual aparte en `build/build-env/` (con `uv` si está
instalado, o con `venv` + `pip` en caso contrario) e instala
allí, únicamente para el empaquetado:

- `pyinstaller>=6.11`
- `pyinstaller-hooks-contrib>=2024.8`
- el propio proyecto y sus dependencias de ejecución (desde `pyproject.toml`)

Así tu `.venv` de desarrollo queda intacto: no se modifican versiones ni se
instalan paquetes nuevos en él.

### Cliente OAuth de Google (para que «Conectar con Google» funcione)

La app no pide `client_secret.json` al usuario: el botón abre el navegador
directamente porque las credenciales del cliente OAuth viajan dentro del
ejecutable. Regístralas **una sola vez**:

1. En [Google Cloud Console](https://console.cloud.google.com/), crea un
   proyecto y activa **Google Calendar API**.
2. Configura la **Pantalla de consentimiento OAuth** (Externo) y añade tu
   cuenta como **usuario de prueba**.
3. **Credenciales → Crear credenciales → ID de cliente de OAuth → Aplicación
   de escritorio**. Descarga el JSON.
4. **Guárdalo como `client_secret.json` en la raíz del proyecto.** Ese nombre
   ya está en `.gitignore`, así que nunca se sube a git.

A partir de ahí todo es automático:

```bash
python3 packaging/build.py
```

El script lee `client_secret.json`, lo normaliza y lo escribe **solo** en el
paquete instalado dentro de `build/build-env/`, así que las credenciales acaban
dentro del ejecutable pero nunca en el código ni en git. El propio script
elimina cualquier `google_client.json` inyectado en builds anteriores.

Orden de búsqueda de credenciales (el primero que exista gana):

1. `CALENDAR_ALARM_GOOGLE_CLIENT_ID` + `CALENDAR_ALARM_GOOGLE_CLIENT_SECRET`
   (lo que usa el CI con secrets del repositorio).
2. Archivo indicado en `CALENDAR_ALARM_GOOGLE_CLIENT_FILE`.
3. `client_secret.json` en la raíz del proyecto (recomendado).
4. `src/calendar_alarm/assets/google_client.json` (también ignorado).

Para desarrollo, sin compilar:

```bash
CALENDAR_ALARM_GOOGLE_CLIENT_FILE=client_secret.json uv run calendar-alarm
```

Si no hay credenciales por ninguna vía, el script de empaquetado avisa y el
botón de la app muestra un error: la build se genera, pero no podrá conectar
con Google.

> Google trata el secreto de un cliente de *Aplicación de escritorio* como no
> confidencial (viaja en el binario). No uses credenciales de tipo
> «Aplicación web»: su secreto sí es confidencial.

### Requisitos en el sistema

Hay dos modos; el script elige solo:

1. **uv** (preferido si está instalado): crea el entorno y reutiliza su caché,
   así que a partir de la segunda compilación no vuelve a descargar PySide6
   (varios cientos de MB). Si no hay un Python 3.11–3.13 en el sistema, uv lo
   descarga. Con `--use-pip` se fuerza el modo 2 aunque uv esté instalado.
2. **Python 3.11–3.13 del sistema con `venv` + `pip`**: debe estar en el
   `PATH` como `python3`, `python` o `python3.13`/`python3.12`/`python3.11`
   (en Windows también vale el lanzador `py -3.13`). El script anula
   `user = true` de un `pip.conf` global, que rompe las instalaciones en venv.
   - Linux/macOS: `curl -LsSf https://astral.sh/uv/install.sh | sh`
   - Windows (PowerShell): `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
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
- **Windows**: un Python 3.11–3.13 (en el `PATH` o vía el lanzador `py`); si no lo tienes, instala uv.

---

## 2. Cómo ejecutar el script en cada sistema

Todos los comandos se lanzan **desde la raíz del proyecto**. Basta con que
exista uv o un Python 3.11–3.13; el intérprete con el que lances el script
puede ser cualquier Python 3 (solo orquesta el build).

### Linux

```bash
python3 packaging/build.py
./dist/calendar-alarm
```

### Windows (PowerShell o CMD)

```powershell
py packaging\build.py      # o: python packaging\build.py
.\dist\CalendarAlarm.exe
```

La primera vez, SmartScreen puede avisar de que el archivo no está firmado:
pulsa **Más información → Ejecutar de todas formas** (el binario es tuyo).

### macOS

```bash
python3 packaging/build.py
open "dist/Calendar Alarm.app"
# o el instalador:
open dist/CalendarAlarm.dmg
```

> Si tu `python3` no es 3.11–3.13 y no tienes uv, usa un intérprete válido
> (`python3.13 packaging/build.py`).

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
| `--use-pip`       | Usa `venv` + `pip` aunque uv esté instalado                   |

---

## 3. Qué hace el script paso a paso

1. Detecta el sistema operativo (`win32`, `darwin` o Linux).
2. Limpia `build/` y `dist/` (salvo `--no-clean`).
3. Crea `build/build-env/` con uv (si está instalado) o con `venv` + `pip`
   a partir de tu Python 3.11–3.13 del sistema.
4. Instala el proyecto limpio y PyInstaller **solo ahí** (`uv pip install` o
   `pip install`).
5. Genera los iconos de la app (PNG, ICO e ICNS) en `build/icons/` mediante
   `packaging/make_icons.py`, dibujados con el mismo diseño de la campana.
6. Ejecuta PyInstaller sobre `packaging/entrypoint.py` incluyendo el paquete
   `calendar_alarm` completo (con `assets/alarm.wav`) y los imports dinámicos
   de Google que PyInstaller no detecta solo. El punto de entrada prepara el
   ejecutable sin consola: redirige `stdout`/`stderr` a un destino nulo si no
   existen (`.exe` con `--windowed`, `.app`), oculta el saludo de pygame y, en
   Windows, fija un AppUserModelID para que la barra de tareas muestre el
   icono de la app.
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

El primer arranque abre la configuración: pulsa **Conectar con Google** (se
abre el navegador), elige la cuenta y autoriza el acceso de solo lectura (si
algo falla en el navegador, **Cancelar** permite reintentar al momento); luego
ajusta el margen de aviso. Los datos de sesión se guardan en el directorio de
configuración del sistema (`~/.config/CalendarAlarm/`,
`%APPDATA%\CalendarAlarm\` o `~/Library/Application Support/CalendarAlarm/`).

---

## 5. Compilar los tres sistemas con GitHub Actions

El repositorio incluye `.github/workflows/build.yml`: al subir un tag `v*` (o
lanzarlo a mano desde **Actions → Build executables → Run workflow**) compila en
Ubuntu, Windows y macOS y publica los artefactos descargables:

1. Sube el proyecto a GitHub (ver sección 7).
2. En **Settings → Secrets and variables → Actions**, crea los secrets
   `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET`. Así los binarios se compilan con
   las credenciales sin que estén en el repositorio.
3. **Actions → Build executables → Run workflow**.
4. Al terminar, descarga los artefactos de la ejecución
   (`calendar-alarm-linux`, `-windows`, `-macos`).
5. Si haces `git push origin v1.0.0`, además se crea una **Release** con los
   binarios adjuntos.

Además, `.github/workflows/tests.yml` pasa ruff, todos los tests (unitarios,
interfaz, integración y empaquetado) y la prueba de humo en los tres sistemas
en cada push y pull request. Los tests de empaquetado comprueban la lógica de
`build.py` para Windows, Linux y macOS sin necesidad de compilar. Detalles en el
apartado «Tests» del [README](README.md).

---

## 6. Notas importantes de distribución

- **Arquitectura**: el binario es nativo de la máquina donde se compila
  (`x86_64` o `arm64`). Para distribuir a equipos ARM (p. ej. Mac con Apple
  Silicon) compílalo en un equipo ARM o con el runner `macos-latest` del CI (Apple Silicon).
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

El proyecto ya es un repositorio git. Crea un repositorio **vacío** en GitHub
(sin README ni licencia, para no tener conflictos) y, desde la raíz del
proyecto:

```bash
git remote add origin https://github.com/TU-USUARIO/calendar-alarm.git
git branch -M master
git push -u origin master
```

Al subirlo se ejecuta solo el workflow **Tests** en Linux, Windows y macOS.
Antes de compilar con CI, crea los secrets de la sección 5.

El `.gitignore` ya excluye `.venv/`, `build/`, `dist/`, cachés y credenciales
(`token.json`, `client_secret*.json`, `google_client.json`). **Nunca subas
`token.json`**: contiene los tokens de acceso de la cuenta conectada.

El `client_id`/`client_secret` de la app **no está en el repositorio**: vive en
`client_secret.json` (ignorado por git) o se pasa al compilar por variables de
entorno / secrets del CI (sección 5). Si rellenas las constantes de
`src/calendar_alarm/oauth_client.py`, ten en cuenta que entonces sí quedarán
visibles en GitHub. Aun así, para un cliente de *Aplicación de escritorio*
Google no lo considera confidencial; lo que nunca debe publicarse es un secreto
de tipo «Aplicación web».

Para publicar una versión con binarios:

```bash
git tag v1.0.0
git push origin v1.0.0
```

---

## 8. Solución de problemas al empaquetar

| Síntoma | Causa / solución |
|---|---|
| `No se encontró un Python 3.13 con venv/pip ni 'uv'` | Instala Python 3.11–3.13 o, si no puedes, uv (que descarga ese Python). |
| `Can not perform a '--user' install` | Tu `pip.conf` tiene `user = true`. El script ya lo anula; si usas pip a mano, añade `PIP_USER=0`. |
| `No matching distribution found for hatchling` | El índice de pip configurado (p. ej. un mirror corporativo) no tiene el paquete. Instala uv o usa `PIP_INDEX_URL=https://pypi.org/simple`. |
| La instalación de dependencias tarda mucho | La primera vez se descargan ~450 MB (PySide6). Con uv las siguientes builds usan la caché. |
| PyInstaller no encuentra `PySide6` | Borra `build/` y vuelve a ejecutar sin `--no-clean`. |
| El `.exe` se abre y se cierra al instante | Compílalo con consola para ver el error: añade temporalmente `--console` a la orden de PyInstaller en `packaging/build.py`. |
| La alarma no suena en el ejecutable | Comprueba que `calendar_alarm/assets/alarm.wav` está en el wheel; el script usa `--collect-data calendar_alarm`. |
| macOS: «app dañada» | Es la cuarentena de Gatekeeper: `xattr -dr com.apple.quarantine "dist/Calendar Alarm.app"`. |
| Linux: falta `libEGL.so.1` | Instala las dependencias gráficas del apartado 1. |
| Icono vacío en Windows | Vuelve a generar iconos: `rm -rf build && python packaging/build.py`. |
