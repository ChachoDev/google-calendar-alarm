from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap


def bell_pixmap(color: str = "#3b82f6", size: int = 64) -> QPixmap:
    """Dibuja una campana de alarma en un pixmap (sin ficheros de imagen del SO)."""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)

    cx = size / 2
    cy = size * 0.54
    r = size * 0.27

    # Cuerpo de la campana (semicírculo superior + base recta redondeada)
    body = QPainterPath()
    body.moveTo(cx - r, cy)
    body.arcTo(QRectF(cx - r, cy - r, 2 * r, 2 * r), 180, 180)
    body.lineTo(cx + r, cy + r * 0.7)
    body.quadTo(cx + r, cy + r, cx + r * 0.78, cy + r)
    body.lineTo(cx - r * 0.78, cy + r)
    body.quadTo(cx - r, cy + r, cx - r, cy + r * 0.7)
    body.closeSubpath()
    painter.drawPath(body)

    # Maza inferior
    painter.drawEllipse(QPointF(cx, cy + r * 1.2), r * 0.22, r * 0.22)

    # Asa superior
    painter.setPen(
        QPen(QColor(color), max(2.0, size * 0.055), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    )
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawArc(
        QRectF(cx - r * 0.24, cy - r * 1.34, r * 0.48, r * 0.5),
        0,
        180 * 16,
    )

    painter.end()
    return pm


def bell_icon(color: str = "#3b82f6", size: int = 64) -> QIcon:
    return QIcon(bell_pixmap(color, size))
