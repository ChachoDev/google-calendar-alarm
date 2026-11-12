# Calendar Alarm — Alarmas de Google Calendar

Aplicación de escritorio multiplataforma (**Windows, Linux y macOS**) escrita en
Python y gestionada con [uv](https://docs.astral.sh/uv/). Suena una alarma
personalizable **antes** de que empiece un evento de Google Calendar.

| Configuración | Aviso de alarma |
|---|---|
| ![Ventana principal](docs/main.png) | ![Ventana de alarma](docs/alarm.png) |

## Características

- **Margen de aviso configurable** por el usuario en horas y minutos
  (por defecto **5 minutos** antes del evento).
- **Hilo de fondo** que consulta la API de Google Calendar periódicamente
  (`google-api-python-client`) sin bloquear la interfaz.
- **Aviso visual prominente** con toda la información del evento: título,
  descripción, ubicación y horario.
- **Sonido en bucle continuo** con `pygame` (sin bloquear la UI), con un
  sonido por defecto incluido y opción de elegir un archivo personalizado
  (`.wav`, `.mp3`, `.ogg`, `.flac`).
- **Icono en la bandeja del sistema** con menú contextual dinámico:
  - Alarma sonando → **Mostrar**, **Parar alarma**, **Salir**.
  - Sin alarma → **Salir**.
  - Clic izquierdo en el icono → abre la ventana (o la alarma si está sonando).
- **Autenticación con Google desde la propia interfaz**: botón para conectar,
  cerrar sesión y cambiar de cuenta.
- Al elegir **Salir** se detiene el audio, se finaliza el hilo de fondo y la
  aplicación termina por completo.

## Requisitos

- Python 3.11–3.13 (uv lo descarga automáticamente si no lo tienes).
- `uv` (https://docs.astral.sh/uv/).

## Instalación

```bash
uv sync
```

`uv sync` crea el entorno virtual, instala la aplicación en modo editable y las
dependencias de desarrollo (ruff) del grupo `dev`.

Calidad de código:

```bash
uv run ruff check src scripts
uv run ruff format src scripts
```

## Ejecutable nativo (Windows / Linux / macOS)

La aplicación se puede distribuir como **ejecutable autocontenido** (incluye
Python, todas las dependencias y los recursos) para el sistema en el que se
compila:

```bash
uv run --no-project python packaging/build.py   # con uv (recomendado)
python3 packaging/build.py                      # sin uv (Python 3.11–3.13)
```

| Sistema  | Resultado                                              |
|----------|--------------------------------------------------------|
| Windows  | `dist/CalendarAlarm.exe`                               |
| Linux    | `dist/calendar-alarm`                                  |
| macOS    | `dist/Calendar Alarm.app` + `dist/CalendarAlarm.dmg`   |

El script crea un entorno de empaquetado **aislado** en `build/build-env/` con
PyInstaller, así que **no altera el `.venv` de desarrollo**. Los iconos se
generan automáticamente (`packaging/make_icons.py`).

Instrucciones completas (dependencias por sistema, cómo arrancar el ejecutable,
firma/cuarentena, límites de `glibc`/arquitectura y compilación de los tres
sistemas con GitHub Actions): **[BUILD.md](BUILD.md)**.

## Configuración de Google Calendar (primera vez)

1. Entra en [Google Cloud Console](https://console.cloud.google.com/).
2. Crea un proyecto nuevo (p. ej. `calendar-alarm`).
3. **APIs y servicios → Biblioteca → Google Calendar API → Activar**.
4. **Pantalla de consentimiento OAuth → Crear → Externo**, rellena el nombre
   del app, tu email de soporte y añade tu cuenta de Gmail como **usuario
   de prueba**.
5. **Credenciales → Crear credenciales → ID de cliente de OAuth**.
   Tipo: **Aplicación de escritorio**. Descarga el JSON.
6. Guarda el archivo como `client_secret.json` (por ejemplo dentro de esta
   carpeta) y selecciónalo en la aplicación con **Examinar…**.

> El archivo `client_secret.json` y el `token.json` generado contienen
> credenciales: nunca los compartas ni los subas a git (ya están en
> `.gitignore`).

## Uso

```bash
uv run calendar-alarm
```

1. Pulsa **Examinar…** y elige tu `client_secret.json`.
2. Pulsa **Conectar con Google** (se abre el navegador) y autoriza el acceso
   de solo lectura a tu calendario.
3. Define el margen de aviso en **horas** y **minutos** (por defecto 0 h 5 min):
   es el tiempo **antes** del inicio del evento en el que arrancará la alarma.
4. Elige tu sonido (o deja el incluido) y pulsa **Probar** si quieres.
5. La aplicación consulta Google Calendar cada 60 s (configurable). Cuando un
   evento esté a menos del margen, sonará la alarma, se mostrará la ventana
   aviso con los datos del evento y la ventana principal se minimizará a la
   bandeja.

### Comportamiento de la bandeja

| Estado            | Menú contextual                  |
|-------------------|----------------------------------|
| Alarma sonando    | **Mostrar**, **Parar alarma**, **Salir** |
| Sin alarma        | **Salir**                        |

- **Mostrar** (solo visible con la alarma activa) abre la ventana de alarma con
  la descripción y los datos relevantes del evento.
- Si la aplicación está en primer plano al sonar, esa misma ventana de alarma
  aparece automáticamente encima de todo.
- Clic izquierdo en el icono: abre la ventana principal (o la de alarma si
  suena).

## Gestores de ventanas de mosaico (Hyprland, i3, sway…)

En un **tiling WM** las ventanas nuevas se colocan en mosaico y el tamaño
solicitado se ignora. La aplicación ya lo tiene en cuenta:

- La **ventana principal** lleva todo su contenido dentro de un área
  desplazable con un mínimo pequeño, así que en un tile estrecho aparecen
  barras de desplazamiento en lugar de recortarse la interfaz.
- La **ventana de alarma** se convierte automáticamente en flotante, se
  centra y se fija (visible en todos los escritorios) cuando se detecta
  Hyprland (`HYPRLAND_INSTANCE_SIGNATURE` + `hyprctl`). Se soportan tanto la
  API Lua de Hyprland ≥ 0.56 (`hl.dsp.window.float/center/pin`) como los
  `dispatch` clásicos de versiones anteriores.

Si prefieres controlarlo desde tu configuración de Hyprland, añade estas
reglas (el comportamiento automático es idempotente y no molesta). Se basan en
el título para funcionar tanto en desarrollo como en el ejecutable:

```ini
windowrulev2 = float,  title:^(Calendar Alarm — AVISO)$
windowrulev2 = center, title:^(Calendar Alarm — AVISO)$
windowrulev2 = pin,    title:^(Calendar Alarm — AVISO)$
```

La clase (`app_id`) de la aplicación es `calendar-alarm` en Linux; en Windows y
macOS es `CalendarAlarm`. También puedes usarla si lo prefieres:
`windowrulev2 = float, class:^(calendar-alarm)$`.

En i3/sway no se hace ninguna integración automática: usa la regla
`for_window [title="Calendar Alarm — AVISO"] floating enable` /
`for_window [...] move position center`.

## Almacenamiento

| Qué                     | Dónde                                                     |
|-------------------------|-----------------------------------------------------------|
| `config.json`           | Linux `~/.config/CalendarAlarm/` · Windows `%APPDATA%\CalendarAlarm\` · macOS `~/Library/Application Support/CalendarAlarm/` |
| `token.json` (sesión)   | Mismo directorio que `config.json`                        |

## Arquitectura

Separación estricta entre lógica de alarma y presentación:

```
src/calendar_alarm/
├── config.py            # Configuración persistente (JSON)
├── models.py            # Modelo CalendarEvent
├── auth.py              # Sesión Google (conectar/desconectar/cambiar cuenta)
├── calendar_service.py  # Consulta a Google Calendar API (+ caché del cliente)
├── workers.py           # Hilo de fondo (QThread) de consultas periódicas
├── alarm_controller.py  # Lógica de alarmas (sin UI): decide cuándo suena
├── audio.py             # Reproducción en bucle con pygame (no bloqueante)
├── app.py               # Composición: une lógica y presentación
├── assets/alarm.wav     # Sonido por defecto incluido
└── ui/
    ├── theme.py         # Estilos (QSS) modernos
    ├── icons.py         # Icono de campana dibujado en tiempo de ejecución
    ├── main_window.py   # Ventana de configuración y autenticación
    ├── alarm_window.py  # Aviso prominente con los datos del evento
    ├── tray.py          # Icono de bandeja y menú contextual dinámico
    ├── hyprland.py      # Integración con Hyprland (flotar/centrar/fijar)
    └── util.py          # Ajuste de ventanas a la pantalla
```

El empaquetado vive en `packaging/` (`build.py` genera el ejecutable nativo,
`make_icons.py` dibuja los iconos y `entrypoint.py` es el punto de entrada de
PyInstaller); los detalles están en [BUILD.md](BUILD.md).

Además, `scripts/generate_default_sound.py` regenera el WAV incluido y
`scripts/smoke_test.py` ejecuta una prueba de humo sin red (arranque, alarma,
menú dinámico y salida limpia):

```bash
uv run python scripts/smoke_test.py
```

Flujo de datos:

```
CalendarWorker (hilo) ──events──▶ AlarmController ──señales──▶ Ventanas / Bandeja
                                        │
                                        └──▶ AudioPlayer (bucle pygame)
```

## Solución de problemas

- **"Sin dispositivo de audio"**: la alarma visual seguirá funcionando;
  revisa que haya un servidor de sonido (PulseAudio/PipeWire, WASAPI, CoreAudio).
- **El navegador no se abre al autenticar**: la consola mostrará una URL;
  ábrela manualmente en tu navegador.
- **Sin eventos**: comprueba que la cuenta conectada sea la correcta
  (botón *Cambiar de cuenta*) y que el evento tenga hora exacta
  (los eventos de todo el día se ignoran).
- **Linux (Wayland)**: la ventana de alarma usa `WindowStaysOnTopHint`;
  en gestores sin soporte puede no quedar siempre encima.

## Licencia

Este proyecto se distribuye bajo la licencia **MIT**. Consulta
[LICENSE](LICENSE).
