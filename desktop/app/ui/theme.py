"""Shared PostGuard visual tokens and Qt Style Sheet (QSS)."""

from PySide6.QtWidgets import QApplication

COLORS = {
    "background": "#f8fafc",
    "surface": "#ffffff",
    "surface_subtle": "#f1f5f9",
    "border": "#e2e8f0",
    "text": "#0f172a",
    "muted": "#64748b",
    "primary": "#2563eb",
    "primary_soft": "#eff6ff",
    "success": "#059669",
    "warning": "#b45309",
    "danger": "#ef4444",
}

APP_QSS = """
QMainWindow, QDialog, QWidget#appRoot, QWidget#authWindow, QStackedWidget#pageStack {
    background: #f8fafc;
    color: #0f172a;
    font-family: "Leelawadee UI", "Noto Sans Thai", "Tahoma", "Segoe UI", sans-serif;
    font-size: 14px;
}
QWidget[page="true"] { background: #f8fafc; }
QWidget#topNavigation {
    background: #ffffff;
    border-bottom: 1px solid #e2e8f0;
}
QLabel#brandLabel { color: #0f172a; font-size: 24px; font-weight: 700; }
QLabel[role="title"] { color: #0f172a; font-size: 24px; font-weight: 700; }
QLabel[role="heading"] { color: #0f172a; font-size: 17px; font-weight: 700; }
QLabel[role="metric"] { color: #0f172a; font-size: 25px; font-weight: 700; }
QLabel[role="muted"] { color: #64748b; }
QLabel[role="eyebrow"] { color: #2563eb; font-size: 11px; font-weight: 700; }
QLabel[role="successIcon"] {
    color: #059669;
    background: #ecfdf5;
    border: 1px solid #a7f3d0;
    border-radius: 24px;
    font-size: 24px;
    font-weight: 700;
}
QLabel[role="infoIcon"] {
    color: #2563eb;
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 24px;
    font-size: 22px;
    font-weight: 700;
}
QLabel[role="warningIcon"] {
    color: #b45309;
    background: #fffbeb;
    border: 1px solid #fcd34d;
    border-radius: 24px;
    font-size: 24px;
    font-weight: 700;
}
QDialog QLabel, QFrame[card="true"] QLabel {
    color: #0f172a;
    background: transparent;
}
QLabel[status="running"] { color: #047857; font-weight: 600; }
QLabel[status="paused"] { color: #b45309; font-weight: 600; }
QLabel[status="idle"] { color: #64748b; }
QFrame[card="true"], QGroupBox {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 14px;
}
QGroupBox {
    margin-top: 12px;
    padding: 18px 14px 14px 14px;
    font-weight: 700;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 5px;
    color: #0f172a;
}
QGroupBox QLabel {
    color: #334155;
    background: transparent;
    font-weight: 400;
}
QFrame[variant="welcome"] {
    background: #eff6ff;
    border: 1px solid #dbeafe;
    border-radius: 16px;
}
QFrame[variant="dangerZone"] {
    background: #fff7f7;
    border: 1px solid #fecaca;
    border-radius: 14px;
}
QFrame[variant="sessionBar"] {
    background: #ffffff;
    border-bottom: 1px solid #e2e8f0;
}
QPushButton {
    min-height: 36px;
    padding: 0 16px;
    color: #0f172a;
    background: #ffffff;
    border: 1px solid #dbe3ee;
    border-radius: 8px;
    font-weight: 600;
}
QPushButton:hover { background: #f1f5f9; border-color: #cbd5e1; }
QPushButton:pressed { background: #e2e8f0; }
QPushButton:disabled { color: #94a3b8; background: #f8fafc; }
QPushButton[variant="primary"] { color: #ffffff; background: #2563eb; border-color: #2563eb; }
QPushButton[variant="primary"]:hover { background: #1d4ed8; }
QPushButton[variant="primary"]:disabled {
    color: #94a3b8;
    background: #f8fafc;
    border-color: #dbe3ee;
}
QPushButton[variant="danger"] { color: #ffffff; background: #ef4444; border-color: #ef4444; }
QPushButton[variant="danger"]:hover { background: #dc2626; }
QPushButton[nav="true"] {
    min-height: 44px;
    padding: 0 12px;
    color: #64748b;
    background: transparent;
    border: 0;
    border-radius: 0;
    font-size: 14px;
}
QPushButton[nav="true"]:hover { color: #0f172a; background: #f8fafc; }
QPushButton[navActive="true"] { color: #0f172a; font-weight: 700; border-bottom: 2px solid #2563eb; }
QLineEdit, QListWidget, QTableWidget, QComboBox, QDoubleSpinBox, QTextBrowser {
    background: #ffffff;
    color: #0f172a;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    selection-background-color: #dbeafe;
    selection-color: #1e3a8a;
}
QTextBrowser { padding: 12px; }
QLineEdit, QComboBox, QDoubleSpinBox {
    min-height: 38px;
    padding: 0 10px;
}
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #2563eb;
}
QComboBox QAbstractItemView {
    color: #0f172a;
    background: #ffffff;
    border: 1px solid #cbd5e1;
    selection-color: #1e3a8a;
    selection-background-color: #dbeafe;
    outline: 0;
}
QCheckBox { color: #334155; spacing: 8px; }
QCheckBox::indicator { width: 17px; height: 17px; }
QListWidget::item { padding: 12px; border-bottom: 1px solid #f1f5f9; }
QListWidget::item:selected { background: #eff6ff; color: #1e40af; }
QTableWidget { gridline-color: #e2e8f0; alternate-background-color: #f8fafc; }
QHeaderView::section {
    background: #f1f5f9;
    color: #475569;
    border: 0;
    border-bottom: 1px solid #e2e8f0;
    padding: 9px;
    font-weight: 600;
}
QScrollArea { border: 0; background: transparent; }
QScrollBar:vertical { background: #f1f5f9; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #cbd5e1; border-radius: 5px; min-height: 28px; }
QLabel[preview="true"] {
    color: #64748b;
    background: #f1f5f9;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
}
QLabel#profileAvatar {
    color: #1e40af;
    background: #dbeafe;
    border: 1px solid #bfdbfe;
    border-radius: 48px;
    font-size: 24px;
    font-weight: 700;
}
QFrame#divider { color: #e2e8f0; background: #e2e8f0; max-height: 1px; }
QToolButton[account="true"] {
    min-width: 42px;
    min-height: 42px;
    color: #1e40af;
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 21px;
    font-weight: 700;
}
QToolButton[account="true"]:hover { background: #dbeafe; }
QToolButton[accountActive="true"] { border: 2px solid #2563eb; }
QMenu {
    color: #0f172a;
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 6px;
}
QMenu::item { padding: 9px 28px 9px 12px; border-radius: 6px; }
QMenu::item:selected { color: #1e40af; background: #eff6ff; }
QMenu::item:disabled { color: #94a3b8; }
"""


def polish(widget) -> None:
    """Re-evaluate QSS selectors after a dynamic property changes."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def set_centered_window(
    widget,
    width: int,
    height: int,
    minimum_width: int,
    minimum_height: int,
) -> None:
    """Set a centered initial size while keeping resize/maximize available."""
    widget.setMinimumSize(minimum_width, minimum_height)
    widget.resize(width, height)
    screen = widget.screen() or QApplication.primaryScreen()
    if screen is None:
        return
    available = screen.availableGeometry()
    widget.move(available.center() - widget.rect().center())
