# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

## [Sin publicar]

### Añadido
- Botón **Cancelar** mientras se espera la autorización de Google en el
  navegador; la denegación del permiso se detecta al momento.
- Suite de tests: unitarios, interfaz, integración, empaquetado y mutación
  (`mutmut`), ejecutada en Linux, Windows y macOS por el workflow `Tests`.
- Variable `CALENDAR_ALARM_CONFIG_DIR` para usar otro directorio de
  configuración.
- Opción `--use-pip` en `packaging/build.py`.

### Cambiado
- `packaging/build.py` usa uv cuando está instalado (más rápido, con caché) y,
  en Windows, encuentra Python con el lanzador `py`.
- La espera de autorización en el navegador caduca a los 5 minutos.

### Corregido
- macOS: ⌘Q y «Salir» del Dock no cerraban la aplicación.
- Salir mientras había una consulta a Google o una conexión en curso podía
  dejar la aplicación colgada.
- El icono de la campana se dibujaba invertido.
- Una sesión de Google caducada o revocada se mostraba como «sin eventos»; ahora
  se avisa de que hay que volver a conectar.
- Un evento movido a otra hora no volvía a avisar.
- `token.json` era legible por otros usuarios en Linux/macOS (ahora `600`).
- Compilación con un `pip.conf` que tiene `user = true`.
- `hdiutil` fallaba a veces con «Resource busy» al crear el `.dmg`.
- Ejecutables sin consola (`.exe`, `.app`) que podían cerrarse si una librería
  escribía en `stdout`/`stderr`.

## [1.0.0]

Primera versión: alarmas de Google Calendar con margen configurable, sonido en
bucle, aviso prominente, icono en la bandeja y ejecutables nativos para
Windows, Linux y macOS.
