from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from calendar_alarm.alarm_controller import AlarmController
from calendar_alarm.audio import AudioPlayer
from calendar_alarm.auth import GoogleAuth
from calendar_alarm.calendar_service import EventFetcher
from calendar_alarm.config import APP_NAME, config_dir, load_config, save_config
from calendar_alarm.ui.alarm_window import AlarmWindow
from calendar_alarm.ui.main_window import MainWindow
from calendar_alarm.ui.theme import APP_QSS
from calendar_alarm.ui.tray import TrayIcon
from calendar_alarm.workers import CalendarWorker


class CalendarAlarmApp:
    """Punto de composición: une el control de alarmas con la presentación."""

    def __init__(self) -> None:
        QApplication.setApplicationName(APP_NAME)
        QApplication.setOrganizationName(APP_NAME)
        QApplication.setDesktopFileName("calendar-alarm")
        # La bandeja mantiene la aplicación viva aunque se cierren las ventanas
        QApplication.setQuitOnLastWindowClosed(False)

        self.app = QApplication(sys.argv)
        # app_id estable en Wayland (Hyprland, sway…): sin esto Qt lo deriva
        # del nombre del ejecutable y cambia entre desarrollo y empaquetado.
        self.app.setStyle("Fusion")
        self.app.setStyleSheet(APP_QSS)

        # ---- lógica (sin UI) -------------------------------------------
        self.config = load_config()
        self.auth = GoogleAuth(config_dir())
        self.audio = AudioPlayer()
        self.controller = AlarmController(self.audio, self.config)

        # ---- presentación ----------------------------------------------
        self.main_window = MainWindow(self.config, self.auth, self.audio)
        self.alarm_window = AlarmWindow()
        self.tray = TrayIcon()

        # ---- hilo de fondo de consultas --------------------------------
        self.worker = CalendarWorker(
            fetch_fn=EventFetcher(self.auth),
            interval_fn=lambda: self.config.poll_interval,
        )
        self.worker.events_ready.connect(self._on_events)
        self.worker.error.connect(self._on_fetch_error)

        self._wire()
        self._start()

    # ------------------------------------------------------------- cableado
    def _wire(self) -> None:
        # Lógica -> presentación
        self.controller.alarm_started.connect(self._on_alarm_started)
        self.controller.alarm_stopped.connect(self._on_alarm_stopped)
        self.controller.audio_error.connect(self._on_audio_error)

        # Presentación -> lógica / ciclo de vida
        self.tray.show_requested.connect(self._show_appropriate)
        self.tray.stop_requested.connect(self.controller.stop)
        self.tray.quit_requested.connect(self.quit)
        self.alarm_window.stop_requested.connect(self.controller.stop)
        self.main_window.quit_requested.connect(self.quit)
        self.main_window.auth_changed.connect(self._on_auth_changed)

        self.app.aboutToQuit.connect(self._shutdown)

    def _start(self) -> None:
        self.main_window.show()
        self.tray.show_message(
            "Calendar Alarm en marcha",
            "Estoy vigilando tu calendario en la bandeja. Clic izquierdo para abrirme.",
        )
        self.worker.start()

    # -------------------------------------------------------------- señales
    def _on_events(self, events: object) -> None:
        event_list = list(events)  # type: ignore[arg-type]
        self.controller.on_events(event_list)
        self.main_window.hide_error()
        if not self.auth.is_authenticated:
            self.main_window.show_events_status(
                "Sin conectar: pulsa «Conectar con Google» para empezar."
            )
            return
        if event_list:
            next_event = event_list[0]
            self.main_window.show_events_status(
                f"{len(event_list)} evento(s) en las próximas 24 h · "
                f"próximo: «{next_event.summary}» a las {next_event.start_str} "
                f"({next_event.date_str})."
            )
        else:
            self.main_window.show_events_status(
                "No hay eventos con hora exacta en las próximas 24 h."
            )
        self.main_window.hide_error()

    def _on_fetch_error(self, message: str) -> None:
        self.main_window.show_error(message)
        if not self.auth.is_authenticated:
            self.main_window.show_events_status(
                "Sin conectar: pulsa «Conectar con Google» para empezar."
            )

    def _on_alarm_started(self, event: object) -> None:
        # Aviso prominente + bandeja en estado "sonando" + minimizar la principal
        self.main_window.hide()
        self.alarm_window.show_event(event)  # type: ignore[arg-type]
        self.tray.set_ringing(True)
        summary = getattr(event, "summary", "")
        start = getattr(event, "start_str", "")
        self.tray.show_message("¡Alarma!", f"{summary} · empieza a las {start}")

    def _on_alarm_stopped(self) -> None:
        self.alarm_window.hide()
        self.tray.set_ringing(False)

    def _on_audio_error(self, message: str) -> None:
        self.main_window.show_error(message)
        self.tray.show_message("Sin sonido", message)

    def _on_auth_changed(self) -> None:
        # Al cambiar de cuenta se olvida el estado de los eventos anteriores
        self.controller.forget_handled()
        if not self.auth.is_authenticated:
            self.controller.stop()
        self.worker.wake()  # consultar de inmediato con la nueva sesión

    def _show_appropriate(self) -> None:
        if self.controller.ringing and self.controller.current_event is not None:
            self.alarm_window.show_event(self.controller.current_event)
            return
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()

    # ------------------------------------------------------------- ciclo de vida
    def quit(self) -> None:
        self.app.quit()

    def _shutdown(self) -> None:
        """Detiene audio, hilo de fondo y guarda la configuración: salida completa."""
        self.worker.stop()
        self.audio.shutdown()
        save_config(self.config)
        self.tray.hide()

    def run(self) -> int:
        return self.app.exec()


def run(argv: list[str] | None = None) -> int:
    return CalendarAlarmApp().run()
