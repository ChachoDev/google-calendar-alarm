from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QCloseEvent, QFontMetrics
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from calendar_alarm.audio import AudioPlayer
from calendar_alarm.auth import GoogleAuth, GoogleAuthError
from calendar_alarm.config import Config, default_sound_path, save_config
from calendar_alarm.ui.icons import bell_icon
from calendar_alarm.ui.theme import APP_QSS
from calendar_alarm.ui.util import fit_to_screen

SECRET_FILTER = "Archivos JSON (*.json);;Todos los archivos (*)"
SOUND_FILTER = (
    "Archivos de sonido (*.wav *.mp3 *.ogg *.flac);;"
    "WAV (*.wav);;MP3 (*.mp3);;OGG (*.ogg);;FLAC (*.flac);;"
    "Todos los archivos (*)"
)
POLL_CHOICES = [30, 60, 120, 300]


class SignInWorker(QThread):
    """Ejecuta el flujo OAuth (servidor local + navegador) fuera del hilo de UI."""

    succeeded = Signal(str)  # correo conectado
    failed = Signal(str)

    def __init__(self, auth: GoogleAuth, client_secret_path: str, parent=None) -> None:
        super().__init__(parent)
        self._auth = auth
        self._path = client_secret_path

    def run(self) -> None:
        try:
            email = self._auth.sign_in(self._path, select_account=True)
        except GoogleAuthError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # errores de red u otros
            self.failed.emit(f"Error inesperado al autenticar: {exc}")
        else:
            self.succeeded.emit(email or "")


class MainWindow(QWidget):
    """Configuración: cuenta de Google, margen de aviso, sonido e intervalo."""

    auth_changed = Signal()
    quit_requested = Signal()

    def __init__(self, config: Config, auth: GoogleAuth, audio: AudioPlayer, parent=None) -> None:
        super().__init__(parent)
        self.config = config
        self.auth = auth
        self.audio = audio
        self._sign_in_worker: SignInWorker | None = None

        self.setWindowTitle("Calendar Alarm — Alarmas de Google Calendar")
        self.setWindowIcon(bell_icon())
        self.setStyleSheet(APP_QSS)

        self._build_ui()
        self.refresh_auth_state()
        self.refresh_sound_label()
        # Tamaño preferido que no recorta el layout ni desborda la pantalla
        fit_to_screen(self, (700, 770))

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Contenido desplazable: en gestores de ventanas de mosaico (Hyprland,
        # i3...) la ventana puede recibir un tile estrecho; con scroll nunca
        # se recorta nada.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setMinimumSize(420, 360)

        content = QWidget()
        content.setObjectName("content")
        root = QVBoxLayout(content)
        root.setContentsMargins(24, 20, 24, 18)
        root.setSpacing(12)

        title = QLabel("Calendar Alarm")
        title.setObjectName("title")
        root.addWidget(title)
        subtitle = QLabel("Te avisa con tiempo antes de que empiece un evento de Google Calendar.")
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        root.addWidget(self._build_account_group())
        root.addWidget(self._build_alarm_group())
        root.addWidget(self._build_status_group())
        root.addStretch(1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        quit_btn = QPushButton("Salir")
        quit_btn.setObjectName("danger")
        quit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        quit_btn.clicked.connect(self.quit_requested.emit)
        footer.addWidget(quit_btn)
        root.addLayout(footer)

        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _build_account_group(self) -> QGroupBox:
        group = QGroupBox("Cuenta de Google")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        top = QHBoxLayout()
        self._auth_status = QLabel("●  No conectada")
        self._auth_status.setObjectName("status-off")
        top.addWidget(self._auth_status)
        top.addStretch(1)
        layout.addLayout(top)

        secret_row = QHBoxLayout()
        secret_row.addWidget(QLabel("client_secret.json:"))
        self._secret_edit = QLineEdit(self.config.client_secret_path)
        self._secret_edit.setReadOnly(True)
        self._secret_edit.setPlaceholderText("Ningún archivo seleccionado")
        secret_row.addWidget(self._secret_edit, 1)
        browse_secret = QPushButton("Examinar…")
        browse_secret.clicked.connect(self._on_browse_secret)
        secret_row.addWidget(browse_secret)
        layout.addLayout(secret_row)

        secret_hint = QLabel(
            "Se genera en Google Cloud Console → Credenciales → OAuth de «Aplicación "
            "de escritorio». El archivo no se sube a ningún sitio: solo se guarda "
            "esta ruta."
        )
        secret_hint.setObjectName("hint")
        secret_hint.setWordWrap(True)
        layout.addWidget(secret_hint)

        actions = QHBoxLayout()
        self._btn_connect = QPushButton("Conectar con Google")
        self._btn_connect.setObjectName("primary")
        self._btn_connect.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_connect.clicked.connect(self._on_sign_in)
        actions.addWidget(self._btn_connect)

        self._btn_change = QPushButton("Cambiar de cuenta")
        self._btn_change.clicked.connect(self._on_sign_in)
        self._btn_change.hide()
        actions.addWidget(self._btn_change)

        self._btn_logout = QPushButton("Cerrar sesión")
        self._btn_logout.setObjectName("danger")
        self._btn_logout.clicked.connect(self._on_sign_out)
        self._btn_logout.hide()
        actions.addWidget(self._btn_logout)
        actions.addStretch(1)
        layout.addLayout(actions)

        self._auth_error = QLabel("")
        self._auth_error.setObjectName("error")
        self._auth_error.setWordWrap(True)
        self._auth_error.hide()
        layout.addWidget(self._auth_error)

        return group

    def _build_alarm_group(self) -> QGroupBox:
        group = QGroupBox("Aviso de alarma")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        warn_row = QHBoxLayout()
        warn_row.addWidget(QLabel("La alarma sonará"))
        self._hours = QSpinBox()
        self._hours.setRange(0, 23)
        self._hours.setValue(self.config.warn_hours)
        self._hours.setSuffix(" h")
        self._hours.valueChanged.connect(self._on_warn_changed)
        warn_row.addWidget(self._hours)
        self._minutes = QSpinBox()
        self._minutes.setRange(0, 59)
        self._minutes.setValue(self.config.warn_minutes)
        self._minutes.setSuffix(" min")
        self._minutes.valueChanged.connect(self._on_warn_changed)
        warn_row.addWidget(self._minutes)
        warn_row.addStretch(1)
        layout.addLayout(warn_row)

        warn_hint = QLabel(
            "La alarma arrancará antes de que empiece el evento: el tiempo indicado "
            "es el que falta para su inicio. Por defecto sonará 5 minutos antes."
        )
        warn_hint.setObjectName("hint")
        warn_hint.setWordWrap(True)
        layout.addWidget(warn_hint)

        sound_row = QHBoxLayout()
        sound_row.addWidget(QLabel("Sonido:"))
        self._sound_label = QLabel("")
        self._sound_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        # Ignorado en el cálculo del mínimo: la ruta se recorta y no debe
        # ensanchar la ventana (si no, se crea un bucle con el tamaño).
        self._sound_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        sound_row.addWidget(self._sound_label, 1)
        btn_sound = QPushButton("Examinar…")
        btn_sound.clicked.connect(self._on_browse_sound)
        sound_row.addWidget(btn_sound)
        layout.addLayout(sound_row)

        sound_buttons = QHBoxLayout()
        btn_default = QPushButton("Usar el de por defecto")
        btn_default.clicked.connect(self._on_default_sound)
        sound_buttons.addWidget(btn_default)
        btn_test = QPushButton("Probar")
        btn_test.clicked.connect(self._on_test_sound)
        sound_buttons.addWidget(btn_test)
        sound_buttons.addStretch(1)
        layout.addLayout(sound_buttons)

        poll_row = QHBoxLayout()
        poll_row.addWidget(QLabel("Consultar Google Calendar cada"))
        self._poll = QComboBox()
        for seconds in POLL_CHOICES:
            self._poll.addItem(f"{seconds} segundos", seconds)
        index = (
            POLL_CHOICES.index(self.config.poll_interval)
            if self.config.poll_interval in POLL_CHOICES
            else 1
        )
        self._poll.setCurrentIndex(index)
        self._poll.currentIndexChanged.connect(self._on_poll_changed)
        poll_row.addWidget(self._poll)
        poll_row.addStretch(1)
        layout.addLayout(poll_row)

        return group

    def _build_status_group(self) -> QGroupBox:
        group = QGroupBox("Estado")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        self._events_status = QLabel("Aún no se ha consultado Google Calendar.")
        self._events_status.setWordWrap(True)
        layout.addWidget(self._events_status)

        self._error_status = QLabel("")
        self._error_status.setObjectName("error")
        self._error_status.setWordWrap(True)
        self._error_status.hide()
        layout.addWidget(self._error_status)

        return group

    # ------------------------------------------------------- autenticación
    def refresh_auth_state(self, email: str | None = None) -> None:
        connected = self.auth.is_authenticated
        email = email if email is not None else (self.auth.account_email if connected else None)

        if connected:
            who = f"Conectado como {email}" if email else "Conectada"
            self._auth_status.setText(f"●  {who}")
            self._auth_status.setObjectName("status-ok")
            self._btn_connect.hide()
            self._btn_change.show()
            self._btn_logout.show()
        else:
            self._auth_status.setText("●  No conectada")
            self._auth_status.setObjectName("status-off")
            self._btn_connect.show()
            self._btn_change.hide()
            self._btn_logout.hide()

        self._auth_status.style().unpolish(self._auth_status)
        self._auth_status.style().polish(self._auth_status)
        self._set_sign_in_busy(False)

    def _set_sign_in_busy(self, busy: bool, message: str = "") -> None:
        for btn in (self._btn_connect, self._btn_change, self._btn_logout):
            btn.setEnabled(not busy)
        if busy:
            self._auth_status.setText(f"●  {message or 'Esperando autorización…'}")
            self._auth_status.setObjectName("status-warn")
            self._auth_status.style().unpolish(self._auth_status)
            self._auth_status.style().polish(self._auth_status)
            self.hide_auth_error()

    def _on_browse_secret(self) -> None:
        start_dir = (
            str(Path(self.config.client_secret_path).parent)
            if self.config.client_secret_path
            else ""
        )
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecciona client_secret.json", start_dir, SECRET_FILTER
        )
        if not path:
            return
        self.config.client_secret_path = path
        save_config(self.config)
        self._secret_edit.setText(path)
        self.hide_auth_error()

    def _on_sign_in(self) -> None:
        if not self.config.client_secret_path or not Path(self.config.client_secret_path).is_file():
            self._on_browse_secret()
            if (
                not self.config.client_secret_path
                or not Path(self.config.client_secret_path).is_file()
            ):
                self.show_auth_error(
                    "Selecciona primero el archivo client_secret.json de Google Cloud."
                )
                return

        self.hide_auth_error()
        self._set_sign_in_busy(True, "Esperando autorización en el navegador…")
        self._sign_in_worker = SignInWorker(self.auth, self.config.client_secret_path, self)
        self._sign_in_worker.succeeded.connect(self._on_sign_in_ok)
        self._sign_in_worker.failed.connect(self._on_sign_in_failed)
        self._sign_in_worker.start()

    def _on_sign_in_ok(self, email: str) -> None:
        self._sign_in_worker = None
        self.refresh_auth_state(email)
        self.show_events_status("Conectado. Consultando los próximos eventos…")
        self.auth_changed.emit()

    def _on_sign_in_failed(self, message: str) -> None:
        self._sign_in_worker = None
        self.refresh_auth_state()
        self.show_auth_error(message)

    def _on_sign_out(self) -> None:
        self.auth.sign_out()
        self.refresh_auth_state()
        self.show_events_status("Sesión cerrada: ya no se consultarán eventos.")
        self.auth_changed.emit()

    def show_auth_error(self, message: str) -> None:
        self._auth_error.setText(message)
        self._auth_error.show()

    def hide_auth_error(self) -> None:
        self._auth_error.hide()

    # ------------------------------------------------------------ ajustes
    def _on_warn_changed(self, _value: int) -> None:
        self.config.warn_hours = self._hours.value()
        self.config.warn_minutes = self._minutes.value()
        save_config(self.config)

    def _on_poll_changed(self, _index: int) -> None:
        self.config.poll_interval = int(self._poll.currentData())
        save_config(self.config)

    def _on_browse_sound(self) -> None:
        start_dir = str(Path(self.config.sound_path).parent) if self.config.sound_path else ""
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecciona un archivo de sonido", start_dir, SOUND_FILTER
        )
        if not path:
            return
        self.config.sound_path = path
        save_config(self.config)
        self.refresh_sound_label()

    def _on_default_sound(self) -> None:
        self.config.sound_path = ""
        save_config(self.config)
        self.refresh_sound_label()

    def _on_test_sound(self) -> None:
        if not self.audio.test(self.config.resolved_sound_path):
            self.show_error(self.audio.last_error or "No se pudo reproducir el sonido.")

    def refresh_sound_label(self) -> None:
        path = self.config.sound_path or f"{default_sound_path()}  (por defecto)"
        available = self._sound_label.width()
        if available < 40:
            available = 220
        elided = QFontMetrics(self._sound_label.font()).elidedText(
            path, Qt.TextElideMode.ElideMiddle, available
        )
        self._sound_label.setText(elided)
        self._sound_label.setToolTip(path)

    # ------------------------------------------------------------- estado
    def show_events_status(self, text: str) -> None:
        self._events_status.setText(text)
        self._events_status.show()

    def show_error(self, message: str) -> None:
        self._error_status.setText(message)
        self._error_status.show()

    def hide_error(self) -> None:
        self._error_status.hide()

    # ------------------------------------------------------------- varios
    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.refresh_sound_label()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.refresh_sound_label()

    def closeEvent(self, event: QCloseEvent) -> None:
        # La ventana se oculta; la aplicación sigue viva en la bandeja.
        event.ignore()
        self.hide()
