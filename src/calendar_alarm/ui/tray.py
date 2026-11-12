from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from calendar_alarm.ui.icons import bell_icon


class TrayIcon(QObject):
    """Icono de bandeja con menú contextual dinámico según el estado de la alarma.

    - Alarma sonando: "Mostrar", "Parar alarma" y "Salir".
    - Sin alarma:     "Salir".
    El clic izquierdo abre la ventana principal (o la de alarma si suena).
    """

    show_requested = Signal()
    stop_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._ringing = False
        self._menu: QMenu | None = None
        self._tray = QSystemTrayIcon(bell_icon("#3b82f6"), self)
        self._tray.setToolTip("Calendar Alarm")
        self._tray.activated.connect(self._on_activated)
        self._tray.messageClicked.connect(self.show_requested.emit)
        self._rebuild_menu()
        self._tray.show()

    # ------------------------------------------------------------- acciones
    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.show_requested.emit()

    # --------------------------------------------------------------- menú
    def _rebuild_menu(self) -> None:
        menu = QMenu()
        if self._ringing:
            show_action = QAction("Mostrar", menu)
            show_action.triggered.connect(self.show_requested.emit)
            menu.addAction(show_action)

            stop_action = QAction("Parar alarma", menu)
            stop_action.triggered.connect(self.stop_requested.emit)
            menu.addAction(stop_action)
            menu.addSeparator()

        quit_action = QAction("Salir", menu)
        quit_action.triggered.connect(self.quit_requested.emit)
        menu.addAction(quit_action)

        old = self._menu
        self._menu = menu
        self._tray.setContextMenu(menu)
        if old is not None:
            old.deleteLater()

    # ------------------------------------------------------------ estado
    def set_ringing(self, ringing: bool) -> None:
        if ringing == self._ringing:
            return
        self._ringing = ringing
        self._tray.setIcon(bell_icon("#ef4444" if ringing else "#3b82f6"))
        self._rebuild_menu()

    def show_message(self, title: str, message: str) -> None:
        self._tray.showMessage(
            title,
            message,
            QSystemTrayIcon.MessageIcon.Information,
            6000,
        )

    def hide(self) -> None:
        self._tray.hide()
