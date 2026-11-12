"""Genera los iconos de la aplicación (PNG, ICO e ICNS) a partir del diseño de la campana.

Se ejecuta SIEMPRE dentro del entorno de empaquetado aislado, nunca con el
entorno de desarrollo. Uso:

    QT_QPA_PLATFORM=offscreen python packaging/make_icons.py --out build/icons
"""

from __future__ import annotations

import argparse
import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Tamaños estándar de icono para escritorio
PNG_SIZES = (16, 24, 32, 48, 64, 128, 256, 512, 1024)
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)
ICNS_TYPES = {
    16: b"icp4",
    32: b"icp5",
    64: b"icp6",
    128: b"ic07",
    256: b"ic08",
    512: b"ic09",
    1024: b"ic10",
}


def render_icon(size: int):
    """Icono cuadrado: baldosa azul redondeada, campana blanca y punto rojo."""
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import (
        QBrush,
        QColor,
        QImage,
        QLinearGradient,
        QPainter,
        QPainterPath,
        QPen,
    )

    from calendar_alarm.ui.icons import bell_pixmap

    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    radius = size * 0.22
    tile = QPainterPath()
    tile.addRoundedRect(QRectF(0, 0, size, size), radius, radius)
    gradient = QLinearGradient(0, 0, size, size)
    gradient.setColorAt(0.0, QColor("#3b82f6"))
    gradient.setColorAt(1.0, QColor("#1d4ed8"))
    painter.fillPath(tile, QBrush(gradient))

    bell = bell_pixmap("#ffffff", max(8, int(size * 0.68)))
    painter.drawPixmap(
        int((size - bell.width()) / 2),
        int((size - bell.height()) / 2 - size * 0.02),
        bell,
    )

    # Punto rojo de notificación
    dot = size * 0.13
    painter.setPen(QPen(QColor("#ffffff"), max(2.0, size * 0.025)))
    painter.setBrush(QColor("#ef4444"))
    painter.drawEllipse(QPointF(size * 0.78, size * 0.22), dot, dot)

    painter.end()
    return image


def _png_bytes(image) -> bytes:
    from PySide6.QtCore import QBuffer, QIODevice

    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    data = bytes(buffer.data())
    buffer.close()
    return data


def write_ico(path: Path, pngs: dict[int, bytes]) -> None:
    """ICO con entradas PNG (compatible con Windows Vista y posteriores)."""
    entries = sorted(pngs.items())
    header = struct.pack("<HHH", 0, 1, len(entries))
    offset = 6 + 16 * len(entries)
    directory = bytearray()
    payload = bytearray()
    for size, png in entries:
        dimension = 0 if size >= 256 else size
        directory += struct.pack("<BBBBHHII", dimension, dimension, 0, 0, 1, 32, len(png), offset)
        offset += len(png)
        payload += png
    path.write_bytes(header + bytes(directory) + bytes(payload))


def write_icns(path: Path, pngs: dict[int, bytes]) -> None:
    """ICNS con chunks PNG (soportado por macOS 10.7+)."""
    body = bytearray()
    for size, kind in ICNS_TYPES.items():
        png = pngs.get(size)
        if png is None:
            continue
        body += kind + struct.pack(">I", len(png) + 8) + png
    path.write_bytes(b"icns" + struct.pack(">I", len(body) + 8) + bytes(body))


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera los iconos de Calendar Alarm.")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("build/icons"),
        help="Directorio de salida (por defecto: build/icons)",
    )
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    from PySide6.QtGui import QGuiApplication

    # Necesaria para QPixmap; se reutiliza si ya existe (tests).
    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])  # noqa: F841

    pngs: dict[int, bytes] = {}
    for size in PNG_SIZES:
        pngs[size] = _png_bytes(render_icon(size))

    png_path = args.out / "CalendarAlarm.png"
    png_path.write_bytes(pngs[1024])

    ico_path = args.out / "CalendarAlarm.ico"
    write_ico(ico_path, {size: pngs[size] for size in ICO_SIZES})

    icns_path = args.out / "CalendarAlarm.icns"
    write_icns(icns_path, pngs)

    print(f"Iconos generados en {args.out}:")
    for path in (png_path, ico_path, icns_path):
        print(f"  - {path.name} ({path.stat().st_size / 1024:.1f} KiB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
