from __future__ import annotations

from PySide6.QtWidgets import QWidget


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
