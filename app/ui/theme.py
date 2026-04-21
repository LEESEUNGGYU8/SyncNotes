from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication


# --- palette ----------------------------------------------------------------

COLOR_BG = "#FFFFFF"
COLOR_BG_SUBTLE = "#FAFAFA"
COLOR_BG_HOVER = "#F0F0F0"
COLOR_BG_SOFT = "#F5F5F5"
COLOR_BORDER = "#EAEAEA"
COLOR_BORDER_STRONG = "#D5D5D5"
COLOR_TEXT = "#1F1F1F"
COLOR_TEXT_SUBTLE = "#6B6B6B"
COLOR_TEXT_MUTED = "#8A8A8A"
COLOR_ACCENT = "#1F1F1F"


# --- font loading -----------------------------------------------------------

def load_application_font(font_path: Path) -> str:
    """Register the Pretendard font with Qt and return its family name.
    Falls back to an empty string if loading fails."""
    if not font_path.exists():
        return ""
    font_id = QFontDatabase.addApplicationFont(str(font_path))
    if font_id < 0:
        return ""
    families = QFontDatabase.applicationFontFamilies(font_id)
    return families[0] if families else ""


# --- stylesheet -------------------------------------------------------------

_QSS_TEMPLATE = """
* {{
    font-family: "{family}", "Pretendard", "Malgun Gothic", "Segoe UI", sans-serif;
    color: {text};
}}

QMainWindow, QDialog {{
    background-color: {bg};
}}

QWidget#ContentRoot {{
    background-color: {bg};
}}

QToolTip {{
    background: #1F1F1F;
    color: #FFFFFF;
    border: none;
    padding: 4px 8px;
    border-radius: 4px;
}}

/* ---- Sticky-Notes style big pill buttons ---- */
QToolButton[primary="true"] {{
    background: {bg_soft};
    border: 1px solid {border};
    border-radius: 10px;
    padding: 10px 18px;
    color: {text};
    font-size: 13px;
    font-weight: 600;
    min-height: 24px;
}}
QToolButton[primary="true"]:hover {{
    background: {bg_hover};
    border-color: {border_strong};
}}
QToolButton[primary="true"]:pressed {{
    background: #E2E2E2;
}}

/* ---- Small icon-only buttons (sticky notes & cards) ---- */
QToolButton[iconOnly="true"] {{
    background: transparent;
    border: none;
    padding: 4px;
    border-radius: 6px;
}}
QToolButton[iconOnly="true"]:hover {{
    background: rgba(0, 0, 0, 0.06);
}}

/* ---- Scrollbars ---- */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 4px 2px 4px 0;
}}
QScrollBar::handle:vertical {{
    background: #D4D4D4;
    border-radius: 5px;
    min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{
    background: #B4B4B4;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
    background: transparent;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}

/* ---- Lists ---- */
QListWidget {{
    background: {bg};
    border: none;
    outline: 0;
    padding: 0;
}}
QListWidget::item {{
    padding: 0;
    margin: 4px 0;
    border: none;
    background: transparent;
}}
QListWidget::item:selected {{
    background: transparent;
}}

/* ---- Inputs ---- */
QLineEdit, QSpinBox, QComboBox {{
    background: #FFFFFF;
    border: 1px solid {border};
    border-radius: 8px;
    padding: 8px 12px;
    selection-background-color: #E3E3E3;
    min-height: 20px;
    font-size: 13px;
    color: {text};
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border-color: {accent};
}}
QSpinBox::up-button, QSpinBox::down-button {{
    width: 0;
    height: 0;
    border: none;
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}

/* ---- Push buttons ---- */
QPushButton {{
    background: {accent};
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 22px;
    font-weight: 600;
    font-size: 13px;
    min-height: 22px;
}}
QPushButton:hover {{
    background: #333333;
}}
QPushButton:pressed {{
    background: #0F0F0F;
}}
QPushButton:default {{
    background: {accent};
}}

/* DialogButtonBox's "Cancel" secondary style */
QDialogButtonBox QPushButton {{
    min-width: 80px;
}}

/* ---- Tabs ---- */
QTabWidget::pane {{
    border: none;
    padding-top: 8px;
}}
QTabBar {{
    qproperty-drawBase: 0;
}}
QTabBar::tab {{
    background: transparent;
    padding: 8px 18px;
    border: none;
    color: {text_subtle};
    font-weight: 600;
    font-size: 13px;
}}
QTabBar::tab:hover {{
    color: {text};
}}
QTabBar::tab:selected {{
    color: {text};
    border-bottom: 2px solid {accent};
}}

/* ---- Status bar ---- */
QStatusBar {{
    background: {bg_subtle};
    border-top: 1px solid {border};
    color: {text_subtle};
    font-size: 11px;
    padding: 2px 12px;
}}
QStatusBar::item {{
    border: none;
}}

/* ---- Labels by role ---- */
QLabel[role="sectionHeader"] {{
    font-size: 12px;
    font-weight: 600;
    color: {text_subtle};
    letter-spacing: 0.3px;
}}
QLabel[role="subtle"] {{
    color: {text_muted};
    font-size: 11px;
}}
QLabel[role="title"] {{
    font-size: 14px;
    font-weight: 700;
    color: {text};
}}

/* ---- Menus ---- */
QMenu {{
    background: #FFFFFF;
    border: 1px solid {border};
    border-radius: 8px;
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 18px;
    border-radius: 6px;
    color: {text};
}}
QMenu::item:selected {{
    background: {bg_hover};
}}
QMenu::separator {{
    height: 1px;
    background: {border};
    margin: 4px 0;
}}

/* ---- FormLayout labels ---- */
QFormLayout > QLabel {{
    color: {text_subtle};
    font-size: 12px;
}}
"""


def build_stylesheet(font_family: str) -> str:
    return _QSS_TEMPLATE.format(
        family=font_family or "Segoe UI",
        bg=COLOR_BG,
        bg_subtle=COLOR_BG_SUBTLE,
        bg_soft=COLOR_BG_SOFT,
        bg_hover=COLOR_BG_HOVER,
        border=COLOR_BORDER,
        border_strong=COLOR_BORDER_STRONG,
        text=COLOR_TEXT,
        text_subtle=COLOR_TEXT_SUBTLE,
        text_muted=COLOR_TEXT_MUTED,
        accent=COLOR_ACCENT,
    )


def apply_theme(app: QApplication, font_family: str) -> None:
    app.setStyleSheet(build_stylesheet(font_family))
    default = QFont(font_family or "Segoe UI", 10)
    app.setFont(default)
