from __future__ import annotations

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QApplication, QWidget

_QUITTING_PROPERTY = "calendarAlarmQuitting"


def mark_quitting() -> None:
    """Indica que la aplicación está saliendo: las ventanas aceptan cerrarse."""
    app = QApplication.instance()
    if app is not None:
        app.setProperty(_QUITTING_PROPERTY, True)


def is_quitting() -> bool:
    app = QApplication.instance()
    return bool(app is not None and app.property(_QUITTING_PROPERTY))


class QuitWatcher(QObject):
    """Detecta la salida pedida por el sistema (⌘Q o «Salir» del Dock en macOS,
    cierre de sesión...). Qt intenta cerrar antes todas las ventanas y, como las
    nuestras ignoran el cierre para seguir en la bandeja, la salida se cancelaría.
    """

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Quit:
            mark_quitting()
        return False


def fit_to_screen(widget: QWidget, preferred: tuple[int, int], margin: int = 40) -> None:
    """Redimensiona una ventana sin recortar el layout ni salir de la pantalla.

    - Nunca por debajo de `minimumSizeHint()` (así no se comprime el contenido).
    - Nunca por encima del área disponible de la pantalla.
    """
    width, height = preferred
    screen = widget.screen()
    if screen is not None:
        available = screen.availableGeometry()
        width = min(width, available.width() - margin)
        height = min(height, available.height() - margin)

    minimum = widget.minimumSizeHint()
    widget.resize(max(width, minimum.width()), max(height, minimum.height()))
