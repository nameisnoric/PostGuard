"""Shared PostGuard visual tokens and Qt Style Sheet (QSS).

This module is UI-only.

It defines:
- Application colors
- Semantic status colors
- Typography
- Cards
- Buttons
- Navigation
- Inputs
- Tables
- Status badges
- Risk badges
- Alert presentation

It must not contain detection, risk, alert-policy,
database, or monitoring business logic.
"""

from PySide6.QtWidgets import QApplication


# ============================================================
# DESIGN TOKENS
# ============================================================

COLORS = {
    # --------------------------------------------------------
    # Base
    # --------------------------------------------------------
    "background": "#f8fafc",
    "surface": "#ffffff",
    "surface_subtle": "#f1f5f9",

    "border": "#e2e8f0",
    "border_strong": "#cbd5e1",

    "text": "#0f172a",
    "text_secondary": "#334155",
    "muted": "#64748b",
    "disabled": "#94a3b8",

    # --------------------------------------------------------
    # Primary / Information
    # --------------------------------------------------------
    "primary": "#2563eb",
    "primary_hover": "#1d4ed8",
    "primary_dark": "#1e40af",
    "primary_soft": "#eff6ff",
    "primary_border": "#bfdbfe",

    # --------------------------------------------------------
    # Success / Normal
    # --------------------------------------------------------
    "success": "#059669",
    "success_dark": "#047857",
    "success_soft": "#ecfdf5",
    "success_border": "#a7f3d0",

    # --------------------------------------------------------
    # Warning / Moderate
    # --------------------------------------------------------
    "warning": "#d97706",
    "warning_dark": "#92400e",
    "warning_soft": "#fffbeb",
    "warning_border": "#fde68a",

    # --------------------------------------------------------
    # Danger / High
    # --------------------------------------------------------
    "danger": "#ef4444",
    "danger_hover": "#dc2626",
    "danger_dark": "#b91c1c",
    "danger_soft": "#fff1f2",
    "danger_border": "#fecdd3",

    # --------------------------------------------------------
    # Informational
    # --------------------------------------------------------
    "info": "#2563eb",
    "info_dark": "#1d4ed8",
    "info_soft": "#eff6ff",
    "info_border": "#bfdbfe",
}


# ============================================================
# APPLICATION QSS
# ============================================================

APP_QSS = """

/* ==========================================================
   ROOT
   ========================================================== */

QMainWindow,
QDialog,
QWidget#appRoot,
QWidget#authWindow,
QStackedWidget#pageStack {
    background: #f8fafc;
    color: #0f172a;

    font-family:
        "Leelawadee UI",
        "Noto Sans Thai",
        "Tahoma",
        "Segoe UI",
        sans-serif;

    font-size: 14px;
}


QWidget[page="true"] {
    background: #f8fafc;
}


/* ==========================================================
   NAVIGATION
   ========================================================== */

QWidget#topNavigation {
    background: #ffffff;
    border-bottom: 1px solid #e2e8f0;
}


QLabel#brandLabel {
    color: #0f172a;

    font-size: 24px;
    font-weight: 700;
}


QPushButton[nav="true"] {
    min-height: 44px;

    padding: 0 12px;

    color: #64748b;

    background: transparent;

    border: 0;
    border-radius: 0;

    font-size: 14px;

    font-weight: 600;
}


QPushButton[nav="true"]:hover {
    color: #0f172a;

    background: #f8fafc;
}


QPushButton[navActive="true"] {
    color: #0f172a;

    font-weight: 700;

    border-bottom: 2px solid #2563eb;
}


/* ==========================================================
   TYPOGRAPHY
   ========================================================== */

QLabel[role="title"] {
    color: #0f172a;

    font-size: 24px;
    font-weight: 700;
}


QLabel[role="heading"] {
    color: #0f172a;

    font-size: 17px;
    font-weight: 700;
}


QLabel[role="subheading"] {
    color: #334155;

    font-size: 15px;
    font-weight: 600;
}


QLabel[role="metric"] {
    color: #0f172a;

    font-size: 26px;
    font-weight: 700;
}


QLabel[role="metricLarge"] {
    color: #0f172a;

    font-size: 32px;
    font-weight: 800;
}


QLabel[role="muted"] {
    color: #64748b;
}


QLabel[role="secondary"] {
    color: #334155;
}


QLabel[role="eyebrow"] {
    color: #2563eb;

    font-size: 11px;

    font-weight: 700;
}


/* ==========================================================
   CARDS
   ========================================================== */

QFrame[card="true"],
QGroupBox {
    background: #ffffff;

    border: 1px solid #e2e8f0;

    border-radius: 14px;
}


QFrame[card="true"] QLabel,
QDialog QLabel {
    background: transparent;
}


QFrame[variant="welcome"] {
    background: #eff6ff;

    border: 1px solid #dbeafe;

    border-radius: 16px;
}


QFrame[variant="sessionBar"] {
    background: #ffffff;

    border-bottom: 1px solid #e2e8f0;
}


QFrame[variant="dangerZone"] {
    background: #fff7f7;

    border: 1px solid #fecaca;

    border-radius: 14px;
}


/* ==========================================================
   METRIC CARDS
   ========================================================== */

QFrame[variant="metricCard"] {
    background: #ffffff;

    border: 1px solid #e5e7eb;

    border-radius: 16px;
}


QFrame[variant="metricCard"][tone="success"] {
    background: #ecfdf5;

    border: 1px solid #a7f3d0;
}


QFrame[variant="metricCard"][tone="warning"] {
    background: #fffbeb;

    border: 1px solid #fde68a;
}


QFrame[variant="metricCard"][tone="danger"] {
    background: #fff1f2;

    border: 1px solid #fecdd3;
}


QFrame[variant="metricCard"][tone="info"] {
    background: #eff6ff;

    border: 1px solid #bfdbfe;
}


/* ==========================================================
   GROUP BOX
   ========================================================== */

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


/* ==========================================================
   STATUS PILLS
   ========================================================== */

QLabel[role="statusPill"] {
    min-height: 28px;

    padding: 0 10px;

    border-radius: 14px;

    font-size: 12px;

    font-weight: 700;
}


QLabel[role="statusPill"][tone="neutral"] {
    color: #475569;

    background: #f1f5f9;

    border: 1px solid #e2e8f0;
}


QLabel[role="statusPill"][tone="info"] {
    color: #1d4ed8;

    background: #eff6ff;

    border: 1px solid #bfdbfe;
}


QLabel[role="statusPill"][tone="success"] {
    color: #047857;

    background: #ecfdf5;

    border: 1px solid #a7f3d0;
}


QLabel[role="statusPill"][tone="warning"] {
    color: #92400e;

    background: #fffbeb;

    border: 1px solid #fde68a;
}


QLabel[role="statusPill"][tone="danger"] {
    color: #b91c1c;

    background: #fff1f2;

    border: 1px solid #fecdd3;
}


/* ==========================================================
   RISK BADGES
   ========================================================== */

QLabel[role="riskBadge"] {
    min-height: 30px;

    padding: 0 12px;

    border-radius: 15px;

    font-size: 12px;

    font-weight: 700;
}


QLabel[role="riskBadge"][risk="NONE"] {
    color: #475569;

    background: #f1f5f9;

    border: 1px solid #e2e8f0;
}


QLabel[role="riskBadge"][risk="LOW"] {
    color: #047857;

    background: #ecfdf5;

    border: 1px solid #a7f3d0;
}


QLabel[role="riskBadge"][risk="MODERATE"] {
    color: #92400e;

    background: #fffbeb;

    border: 1px solid #fde68a;
}


QLabel[role="riskBadge"][risk="HIGH"] {
    color: #b91c1c;

    background: #fff1f2;

    border: 1px solid #fecdd3;
}


/* ==========================================================
   STATUS TEXT — LEGACY SUPPORT
   ========================================================== */

QLabel[status="running"] {
    color: #047857;

    font-weight: 600;
}


QLabel[status="paused"] {
    color: #b45309;

    font-weight: 600;
}


QLabel[status="idle"] {
    color: #64748b;
}


QLabel[status="error"] {
    color: #b91c1c;

    font-weight: 600;
}


/* ==========================================================
   ICON BADGES
   ========================================================== */

QLabel[role="successIcon"],
QLabel[role="infoIcon"],
QLabel[role="warningIcon"],
QLabel[role="dangerIcon"],
QLabel[role="alertIcon"] {
    min-width: 36px;
    min-height: 36px;

    max-width: 36px;
    max-height: 36px;

    border-radius: 18px;

    font-size: 20px;

    font-weight: 800;
}


QLabel[role="successIcon"] {
    color: #059669;

    background: #ecfdf5;

    border: 1px solid #a7f3d0;
}


QLabel[role="infoIcon"] {
    color: #2563eb;

    background: #eff6ff;

    border: 1px solid #bfdbfe;
}


QLabel[role="warningIcon"] {
    color: #b45309;

    background: #fffbeb;

    border: 1px solid #fde68a;
}


QLabel[role="dangerIcon"] {
    color: #b91c1c;

    background: #fff1f2;

    border: 1px solid #fecdd3;
}


QLabel[role="alertIcon"][tone="info"] {
    color: #1d4ed8;

    background: #eff6ff;

    border: 1px solid #bfdbfe;
}


QLabel[role="alertIcon"][tone="warning"] {
    color: #92400e;

    background: #fffbeb;

    border: 1px solid #fde68a;
}


QLabel[role="alertIcon"][tone="danger"] {
    color: #b91c1c;

    background: #fff1f2;

    border: 1px solid #fecdd3;
}


/* ==========================================================
   ALERT CARDS
   ========================================================== */

QFrame[severity="info"] {
    background: #ffffff;

    border: 1px solid #dbeafe;

    border-left: 4px solid #2563eb;

    border-radius: 14px;
}


QFrame[severity="warning"] {
    background: #ffffff;

    border: 1px solid #fde68a;

    border-left: 4px solid #d97706;

    border-radius: 14px;
}


QFrame[severity="danger"] {
    background: #ffffff;

    border: 1px solid #fecdd3;

    border-left: 4px solid #dc2626;

    border-radius: 14px;
}


/* ==========================================================
   BUTTONS
   ========================================================== */

QPushButton {
    min-height: 38px;

    padding: 0 16px;

    color: #0f172a;

    background: #ffffff;

    border: 1px solid #dbe3ee;

    border-radius: 9px;

    font-weight: 600;
}


QPushButton:hover {
    background: #f1f5f9;

    border-color: #cbd5e1;
}


QPushButton:pressed {
    background: #e2e8f0;
}


QPushButton:disabled {
    color: #94a3b8;

    background: #f8fafc;

    border-color: #e2e8f0;
}


/* ----------------------------------------------------------
   Primary
   ---------------------------------------------------------- */

QPushButton[variant="primary"] {
    color: #ffffff;

    background: #2563eb;

    border-color: #2563eb;
}


QPushButton[variant="primary"]:hover {
    background: #1d4ed8;

    border-color: #1d4ed8;
}


QPushButton[variant="primary"]:disabled {
    color: #94a3b8;

    background: #f8fafc;

    border-color: #dbe3ee;
}


/* ----------------------------------------------------------
   Danger
   ---------------------------------------------------------- */

QPushButton[variant="danger"] {
    color: #ffffff;

    background: #ef4444;

    border-color: #ef4444;
}


QPushButton[variant="danger"]:hover {
    background: #dc2626;

    border-color: #dc2626;
}


/* ----------------------------------------------------------
   Success
   ---------------------------------------------------------- */

QPushButton[variant="success"] {
    color: #ffffff;

    background: #059669;

    border-color: #059669;
}


QPushButton[variant="success"]:hover {
    background: #047857;

    border-color: #047857;
}


/* ----------------------------------------------------------
   Warning
   ---------------------------------------------------------- */

QPushButton[variant="warning"] {
    color: #92400e;

    background: #fffbeb;

    border-color: #fde68a;
}


QPushButton[variant="warning"]:hover {
    background: #fef3c7;

    border-color: #fcd34d;
}


/* ----------------------------------------------------------
   Ghost
   ---------------------------------------------------------- */

QPushButton[variant="ghost"] {
    color: #475569;

    background: transparent;

    border: 0;
}


QPushButton[variant="ghost"]:hover {
    color: #0f172a;

    background: #f1f5f9;
}


/* ==========================================================
   INPUTS
   ========================================================== */

QLineEdit,
QListWidget,
QTableWidget,
QComboBox,
QDoubleSpinBox,
QSpinBox,
QTextBrowser {
    background: #ffffff;

    color: #0f172a;

    border: 1px solid #e2e8f0;

    border-radius: 8px;

    selection-background-color: #dbeafe;

    selection-color: #1e3a8a;
}


QTextBrowser {
    padding: 12px;
}


QLineEdit,
QComboBox,
QDoubleSpinBox,
QSpinBox {
    min-height: 38px;

    padding: 0 10px;
}


QLineEdit:focus,
QComboBox:focus,
QDoubleSpinBox:focus,
QSpinBox:focus {
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


/* ==========================================================
   CHECKBOX
   ========================================================== */

QCheckBox {
    color: #334155;

    spacing: 8px;
}


QCheckBox::indicator {
    width: 17px;

    height: 17px;
}


/* ==========================================================
   LIST
   ========================================================== */

QListWidget::item {
    padding: 12px;

    border-bottom: 1px solid #f1f5f9;
}


QListWidget::item:selected {
    background: #eff6ff;

    color: #1e40af;
}


/* ==========================================================
   TABLE
   ========================================================== */

QTableWidget {
    gridline-color: #e2e8f0;

    alternate-background-color: #f8fafc;
}


QHeaderView::section {
    background: #f1f5f9;

    color: #475569;

    border: 0;

    border-bottom: 1px solid #e2e8f0;

    padding: 9px;

    font-weight: 600;
}


/* ==========================================================
   SCROLL
   ========================================================== */

QScrollArea {
    border: 0;

    background: transparent;
}


QScrollBar:vertical {
    background: #f1f5f9;

    width: 10px;

    margin: 0;
}


QScrollBar::handle:vertical {
    background: #cbd5e1;

    border-radius: 5px;

    min-height: 28px;
}


QScrollBar::handle:vertical:hover {
    background: #94a3b8;
}


/* ==========================================================
   CAMERA / PREVIEW
   ========================================================== */

QLabel[preview="true"] {
    color: #64748b;

    background: #f1f5f9;

    border: 1px solid #e2e8f0;

    border-radius: 14px;
}


/* ==========================================================
   PROFILE
   ========================================================== */

QLabel#profileAvatar {
    color: #1e40af;

    background: #dbeafe;

    border: 1px solid #bfdbfe;

    border-radius: 48px;

    font-size: 24px;

    font-weight: 700;
}


QToolButton[account="true"] {
    min-width: 42px;
    min-height: 42px;

    color: #1e40af;

    background: #eff6ff;

    border: 1px solid #bfdbfe;

    border-radius: 21px;

    font-weight: 700;
}


QToolButton[account="true"]:hover {
    background: #dbeafe;
}


QToolButton[accountActive="true"] {
    border: 2px solid #2563eb;
}


/* ==========================================================
   DIVIDER
   ========================================================== */

QFrame#divider {
    color: #e2e8f0;

    background: #e2e8f0;

    max-height: 1px;
}


/* ==========================================================
   MENU
   ========================================================== */

QMenu {
    color: #0f172a;

    background: #ffffff;

    border: 1px solid #e2e8f0;

    border-radius: 8px;

    padding: 6px;
}


QMenu::item {
    padding: 9px 28px 9px 12px;

    border-radius: 6px;
}


QMenu::item:selected {
    color: #1e40af;

    background: #eff6ff;
}


QMenu::item:disabled {
    color: #94a3b8;
}


/* ==========================================================
   TOOLTIP
   ========================================================== */

QToolTip {
    color: #ffffff;

    background: #0f172a;

    border: 0;

    padding: 6px;

    border-radius: 6px;
}

"""


# ============================================================
# UI HELPERS
# ============================================================

def polish(widget) -> None:
    """
    Re-evaluate QSS selectors after a dynamic property changes.

    Example:
        label.setProperty("tone", "danger")
        polish(label)
    """

    if widget is None:
        return

    style = widget.style()

    if style is None:
        return

    style.unpolish(widget)
    style.polish(widget)

    widget.update()


def set_centered_window(
    widget,
    width: int,
    height: int,
    minimum_width: int,
    minimum_height: int,
) -> None:
    """
    Set a centered initial window size while keeping resize/maximize
    available.
    """

    widget.setMinimumSize(
        minimum_width,
        minimum_height,
    )

    widget.resize(
        width,
        height,
    )

    screen = (
        widget.screen()
        or QApplication.primaryScreen()
    )

    if screen is None:
        return

    available = (
        screen.availableGeometry()
    )

    widget.move(
        available.center()
        - widget.rect().center()
    )