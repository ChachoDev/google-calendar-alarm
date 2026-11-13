from __future__ import annotations

# Tema oscuro moderno y transversal (Windows / Linux / macOS)
APP_QSS = """
* { font-family: "Segoe UI", "SF Pro Text", "Inter", "Noto Sans", sans-serif; }
QWidget { background: #0f1115; color: #e6e8ee; font-size: 13px; }
/* Las etiquetas deben ser transparentes: si no, cada una pinta su propio
   fondo oscuro sobre las tarjetas y se ve un recuadro detrás del texto. */
QLabel { background: transparent; }
QFrame { background: transparent; }

QLabel#title { font-size: 24px; font-weight: 700; color: #ffffff; }
QLabel#subtitle { color: #8b93a7; font-size: 13px; }
QLabel#hint { color: #8b93a7; font-size: 12px; }
QLabel#status-ok { color: #34d399; font-weight: 600; }
QLabel#status-warn { color: #fbbf24; font-weight: 600; }
QLabel#status-off { color: #94a3b8; font-weight: 600; }
QLabel#error { color: #f87171; font-size: 12px; }

QGroupBox {
    background: #161a21;
    border: 1px solid #232833;
    border-radius: 14px;
    margin-top: 18px;
    padding: 14px 16px 12px 16px;
    font-weight: 600;
    font-size: 14px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 16px;
    top: 4px;
    padding: 0 8px;
    color: #7dd3fc;
    background: #0f1115;
}

QPushButton {
    background: #242b39;
    border: 1px solid #2f3849;
    border-radius: 10px;
    padding: 9px 16px;
    font-weight: 600;
    color: #e6e8ee;
}
QPushButton:hover { background: #2c3546; border-color: #3c4761; }
QPushButton:pressed { background: #1d2431; }
QPushButton:disabled { background: #171b23; color: #5b6474; border-color: #1f242e; }

QPushButton#primary { background: #2563eb; border-color: #2563eb; color: #ffffff; }
QPushButton#primary:hover { background: #3b82f6; border-color: #3b82f6; }
QPushButton#primary:pressed { background: #1d4ed8; }
QPushButton#primary:disabled { background: #1c2a44; border-color: #1c2a44; color: #5c7ab8; }

QPushButton#danger { background: #3a1c22; border-color: #7f1d1d; color: #fca5a5; }
QPushButton#danger:hover { background: #4a222a; border-color: #991b1b; }
QPushButton#danger:disabled { background: #241619; border-color: #241619; color: #6b454b; }

QLineEdit, QSpinBox, QComboBox {
    background: #0b0d12;
    border: 1px solid #2a3140;
    border-radius: 9px;
    padding: 8px 11px;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
}
/* Los QSpinBox necesitan más aire a la izquierda y hueco para las flechas. */
QSpinBox { padding-left: 14px; padding-right: 26px; }
QLineEdit:focus, QSpinBox:focus, QComboBox:focus { border-color: #3b82f6; }
QLineEdit:read-only { color: #aab2c5; }
QSpinBox::up-button, QSpinBox::down-button { width: 18px; background: transparent; border: none; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView {
    background: #161a21;
    border: 1px solid #2a3140;
    selection-background-color: #2563eb;
    outline: none;
}

QLabel#big-value { font-size: 22px; font-weight: 700; color: #ffffff; }

QStatusBar { background: #0b0d12; color: #8b93a7; border-top: 1px solid #1c212b; }
QToolTip { background: #1c212b; color: #e6e8ee; border: 1px solid #2a3140; padding: 4px; }

QScrollArea { background: #0f1115; border: none; }
QScrollArea > QWidget > QWidget { background: #0f1115; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #2a3140; border-radius: 5px; min-height: 28px; }
QScrollBar::handle:vertical:hover { background: #3c4761; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
"""

# Ventana de alarma: aviso prominente en tono rojo
ALARM_QSS = """
QWidget#alarmRoot {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #1b0f14, stop:0.55 #14111a, stop:1 #0f0d14);
}
QLabel#alarmBadge {
    background: #dc2626;
    color: #ffffff;
    border-radius: 14px;
    padding: 7px 20px;
    font-size: 15px;
    font-weight: 800;
    letter-spacing: 3px;
}
QLabel#alarmBadge.alt { background: #f87171; }
QLabel#alarmTitle { font-size: 30px; font-weight: 800; color: #ffffff; }
QLabel#alarmMeta { font-size: 15px; color: #fda4af; font-weight: 600; }
QLabel#alarmWhen { font-size: 17px; color: #ffe4e6; font-weight: 700; }
QLabel#alarmSection {
    color: #94a3b8;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 1px;
}
QFrame#alarmCard {
    background: #1a1218;
    border: 1px solid #3b1b22;
    border-radius: 14px;
}
QLabel#alarmBody { color: #e2e8f0; font-size: 14px; }
QScrollArea { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical {
    background: #3b1b22; border-radius: 5px; min-height: 24px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QPushButton#stop {
    background: #dc2626;
    border: none;
    border-radius: 14px;
    padding: 16px;
    font-size: 17px;
    font-weight: 800;
    color: #ffffff;
}
QPushButton#stop:hover { background: #ef4444; }
QPushButton#stop:pressed { background: #b91c1c; }
QLabel#alarmHint { color: #94a3b8; font-size: 12px; }
"""
