# Contribuir a Calendar Alarm

## Preparar el entorno

Necesitas [uv](https://docs.astral.sh/uv/) (descarga Python 3.13 si no lo
tienes):

```bash
uv sync                      # entorno + dependencias de desarrollo
uv run calendar-alarm        # arrancar la app
```

Para conectar con Google en desarrollo necesitas un cliente OAuth de tipo
*Aplicación de escritorio* guardado como `client_secret.json` en la raíz (está
en `.gitignore`):

```bash
CALENDAR_ALARM_GOOGLE_CLIENT_FILE=client_secret.json uv run calendar-alarm
```

Usa `CALENDAR_ALARM_CONFIG_DIR=/tmp/calendar-alarm-dev` si no quieres tocar tu
configuración ni tu sesión reales.

## Antes de abrir un pull request

```bash
uv run ruff check src tests scripts packaging
uv run ruff format src tests scripts packaging
uv run pytest                # debe pasar entero
uv run mutmut run            # si cambias lógica (Linux/macOS)
```

- Todo cambio de comportamiento lleva su test. La lógica sin interfaz va en
  `tests/unit/`; las ventanas, en `tests/ui/`; el empaquetado, en
  `tests/packaging/`. El apartado «Tests» del [README](README.md) explica cada
  tipo.
- Si `mutmut results` muestra un mutante nuevo que sobrevive, añade un test que
  lo detecte o explica en el PR por qué es equivalente.
- La app debe seguir funcionando en **Windows, Linux y macOS**: el workflow
  `Tests` lo comprueba en los tres sistemas.
- Si cambias el empaquetado, prueba `python packaging/build.py` en tu sistema y
  lanza **Build executables** desde Actions para los demás.
- Actualiza `README.md`, `BUILD.md` y `CHANGELOG.md` cuando cambie algo visible.

## Seguridad

Nunca subas `client_secret.json`, `token.json` ni `google_client.json`. Si
encuentras un problema de seguridad, no abras un issue público: escribe al
responsable del repositorio.
