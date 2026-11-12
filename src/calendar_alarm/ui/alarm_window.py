from __future__ import annotations

import sys

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QKeyEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from calendar_alarm.models import CalendarEvent
from calendar_alarm.ui.hyprland import (
    center_alarm_window,
    float_alarm_window,
    is_hyprland,
    pin_alarm_window,
    resize_alarm_window,
)
from calendar_alarm.ui.theme import ALARM_QSS
from calendar_alarm.ui.util import fit_to_screen, is_quitting


class AlarmWindow(QWidget):
    """Aviso prominente con los datos relevantes del evento que dispara la alarma."""

    stop_requested = Signal()

    def __init__(self, parent=None) -> None:
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Dialog
        )
        if sys.platform == "win32":
            # En Windows no queremos entrada propia en la barra de tareas
            flags |= Qt.WindowType.Tool
        super().__init__(parent, flags)

        self.setObjectName("alarmRoot")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setWindowTitle("Calendar Alarm — AVISO")
        self.setMinimumSize(620, 440)
        self.setStyleSheet(ALARM_QSS)

        self._build_ui()

        # Parpadeo del distintivo "ALARMA" para que resulte imposible ignorar
        self._pulse_on = False
        self._pulse = QTimer(self)
        self._pulse.setInterval(550)
        self._pulse.timeout.connect(self._toggle_pulse)

    # ------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(34, 26, 34, 26)
        root.setSpacing(14)

        header = QHBoxLayout()
        self._badge = QLabel("A L A R M A")
        self._badge.setObjectName("alarmBadge")
        header.addWidget(self._badge)
        header.addStretch(1)
        self._when = QLabel("")
        self._when.setObjectName("alarmWhen")
        header.addWidget(self._when)
        root.addLayout(header)

        self._title = QLabel("—")
        self._title.setObjectName("alarmTitle")
        self._title.setWordWrap(True)
        root.addWidget(self._title)

        meta = QHBoxLayout()
        self._location = QLabel("")
        self._location.setObjectName("alarmMeta")
        self._location.setWordWrap(True)
        meta.addWidget(self._location, 1)
        root.addLayout(meta)

        card = QFrame()
        card.setObjectName("alarmCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(8)

        desc_label = QLabel("DESCRIPCIÓN DEL EVENTO")
        desc_label.setObjectName("alarmSection")
        card_layout.addWidget(desc_label)

        self._description = QLabel("Sin descripción.")
        self._description.setObjectName("alarmBody")
        self._description.setWordWrap(True)
        self._description.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._description.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._description)
        scroll.setMinimumHeight(120)
        # El viewport interno del scroll hereda el fondo global oscuro; aquí
        # debe ser transparente para no pintar un rectángulo sobre la tarjeta.
        scroll.setStyleSheet(
            "QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }"
        )
        scroll.viewport().setAutoFillBackground(False)
        self._description.setAutoFillBackground(False)
        card_layout.addWidget(scroll, 1)
        root.addWidget(card, 1)

        self._hint = QLabel(
            "La alarma seguirá sonando en bucle hasta que la detengas (Esc o el botón)."
        )
        self._hint.setObjectName("alarmHint")
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._hint)

        self._stop_btn = QPushButton("Parar alarma")
        self._stop_btn.setObjectName("stop")
        self._stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._stop_btn.clicked.connect(self.stop_requested.emit)
        root.addWidget(self._stop_btn)

    # ---------------------------------------------------------- eventos
    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.stop_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        # Cerrar la ventana no detiene la alarma: hay que pulsar "Parar alarma".
        if is_quitting():
            event.accept()
            return
        event.ignore()
        self.hide()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self.stop_pulse()

    def _toggle_pulse(self) -> None:
        self._pulse_on = not self._pulse_on
        self._badge.setProperty("alt", self._pulse_on)
        self._badge.style().unpolish(self._badge)
        self._badge.style().polish(self._badge)

    # ---------------------------------------------------------- mostrar
    def show_event(self, event: CalendarEvent) -> None:
        self._title.setText(event.summary or "(Sin título)")
        self._when.setText(event.schedule_str())
        self._location.setText(f"Ubicación: {event.location}" if event.location else "")
        self._location.setVisible(bool(event.location))
        self._description.setText(event.description or "Sin descripción.")

        # Tamaño preferido sin recortar el layout y dentro de la pantalla
        fit_to_screen(self, (720, 540))

        # Centrar en la pantalla donde está el cursor
        screen = self.screen()
        if screen is not None:
            geo = screen.availableGeometry()
            self.move(
                geo.center().x() - self.width() // 2,
                geo.center().y() - self.height() // 2,
            )
        self.show()
        self.raise_()
        self.activateWindow()
        self._stop_btn.setFocus()
        # El parpadeo solo corre mientras la ventana está visible.
        self._pulse.start()

        # En Hyprland (tiling) hay que convertirla en flotante y centrarla;
        # se hace justo después del mapeo para que el WM actúe sobre ella.
        if is_hyprland():
            QTimer.singleShot(150, self._float_on_hyprland)
            QTimer.singleShot(400, self._center_and_pin)

    def _float_on_hyprland(self) -> None:
        if self.isVisible():
            float_alarm_window(self.windowTitle())

    def _center_and_pin(self) -> None:
        if not self.isVisible():
            return
        # Qt no propaga el tamaño a una ventana flotante en Wayland: se fija
        # el tamaño exacto por hyprctl y después se centra y se fija.
        width, height = self._desired_size()
        if not resize_alarm_window(self.windowTitle(), width, height):
            self._resize_centered()
        center_alarm_window(self.windowTitle())
        pin_alarm_window(self.windowTitle())

    def _desired_size(self) -> tuple[int, int]:
        width, height = 720, 540
        screen = self.screen()
        if screen is not None:
            available = screen.availableGeometry()
            width = min(width, available.width() - 40)
            height = min(height, available.height() - 40)
        minimum = self.minimumSizeHint()
        return max(width, minimum.width()), max(height, minimum.height())

    def _resize_centered(self) -> None:
        if not self.isVisible():
            return
        fit_to_screen(self, (720, 540))
        screen = self.screen()
        if screen is not None:
            geo = screen.availableGeometry()
            self.move(
                geo.center().x() - self.width() // 2,
                geo.center().y() - self.height() // 2,
            )

    def stop_pulse(self) -> None:
        self._pulse.stop()
        self._badge.setProperty("alt", False)
        self._badge.style().unpolish(self._badge)
        self._badge.style().polish(self._badge)
