from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QWidget

from calendar_alarm.ui import util
from calendar_alarm.ui.icons import bell_icon, bell_pixmap


def reset_quitting():
    QApplication.instance().setProperty(util._QUITTING_PROPERTY, False)


def test_mark_quitting(qapp):
    reset_quitting()
    assert util.is_quitting() is False
    util.mark_quitting()
    assert util.is_quitting() is True
    reset_quitting()


def test_quit_watcher_detecta_la_salida_del_sistema(qapp):
    reset_quitting()
    watcher = util.QuitWatcher()
    assert watcher.eventFilter(qapp, QEvent(QEvent.Type.Quit)) is False  # no la consume
    assert util.is_quitting() is True
    reset_quitting()
    assert watcher.eventFilter(qapp, QEvent(QEvent.Type.Show)) is False
    assert util.is_quitting() is False


def test_fit_to_screen_respeta_minimo_y_pantalla(qapp):
    widget = QWidget()
    widget.setMinimumSize(300, 200)
    util.fit_to_screen(widget, (100, 100))
    assert (widget.width(), widget.height()) == (300, 200)

    available = widget.screen().availableGeometry()
    util.fit_to_screen(widget, (100000, 100000), margin=40)
    assert widget.width() <= available.width() - 40
    assert widget.height() <= available.height() - 40


def test_bell_pixmap_tamano_y_color(qapp):
    pm = bell_pixmap("#ff0000", 64)
    assert (pm.width(), pm.height()) == (64, 64)
    image = pm.toImage()
    colors = [QColor.fromRgba(image.pixel(x, y)) for x in range(64) for y in range(64)]
    painted = [c for c in colors if c.alpha() == 255]
    assert len(painted) > 64 * 64 * 0.15  # la campana ocupa buena parte del icono
    assert all(c.red() > 200 and c.green() < 60 and c.blue() < 60 for c in painted)
    # La cúpula queda por encima del centro (antes salía invertida, como una taza).
    assert QColor.fromRgba(image.pixel(32, 26)).alpha() == 255
    assert QColor.fromRgba(image.pixel(32, 40)).alpha() == 255
    corner = QColor.fromRgba(image.pixel(0, 0))
    assert corner.alpha() == 0  # fondo transparente


def test_bell_icon_no_vacio(qapp):
    assert not bell_icon().isNull()
    assert QCoreApplication.instance() is qapp
