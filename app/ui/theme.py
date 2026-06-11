from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPainter, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QScrollBar,
    QStyle,
    QStyleOptionSlider,
)

from .. import config


class RoundedScrollBar(QScrollBar):
    """핸들을 항상 둥글게 표시하는 세로 스크롤바.

    Windows 네이티브 스타일이 QSS 의 border-radius 를 무시하고 핸들을 각지게
    그리므로, 스타일이 계산한 슬라이더 영역에 알약형 핸들을 직접 페인팅한다.
    슬라이더 영역을 그대로 쓰므로 드래그 히트 영역과 그림이 어긋나지 않는다."""

    def __init__(self, handle: str = "#D4D4D4", hover: str = "#B4B4B4",
                 parent=None) -> None:
        super().__init__(Qt.Vertical, parent)
        self._handle = QColor(handle)
        self._hover = QColor(hover)
        self._hovered = False
        self.setMouseTracking(True)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def set_colors(self, handle, hover) -> None:
        self._handle = QColor(handle)
        self._hover = QColor(hover)
        self.update()

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def _slider_rect(self):
        opt = QStyleOptionSlider()
        opt.initFrom(self)
        opt.orientation = Qt.Vertical
        opt.minimum = self.minimum()
        opt.maximum = self.maximum()
        opt.sliderPosition = self.sliderPosition()
        opt.sliderValue = self.value()
        opt.pageStep = self.pageStep()
        opt.singleStep = self.singleStep()
        return self.style().subControlRect(
            QStyle.CC_ScrollBar, opt, QStyle.SC_ScrollBarSlider, self)

    def paintEvent(self, event) -> None:  # noqa: N802
        if self.minimum() >= self.maximum():
            return
        rect = self._slider_rect()
        if rect.width() <= 0 or rect.height() <= 0:
            return
        r = QRectF(rect).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = r.width() / 2.0
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        active = self._hovered or self.isSliderDown()
        painter.setBrush(self._hover if active else self._handle)
        painter.drawRoundedRect(r, radius, radius)
        painter.end()


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


def load_application_font(font_path: Path) -> str:
    if not font_path.exists():
        return ""
    font_id = QFontDatabase.addApplicationFont(str(font_path))
    if font_id < 0:
        return ""
    families = QFontDatabase.applicationFontFamilies(font_id)
    return families[0] if families else ""


def load_application_fonts(language: str) -> str:
    """언어별 기본 family 를 반환한다.

    두 폰트를 모두 등록해 둬야 혼용 텍스트(예: 한국어 UI 안의 일본어 메모)가
    폴백 체인으로 올바르게 렌더링된다."""
    ko_family = load_application_font(config.FONT_PATH)
    jp_family = load_application_font(config.FONT_PATH_JP)
    if language == "ja" and jp_family:
        return jp_family
    return ko_family or jp_family


# 본문용 폰트 스택. 한·일 혼용을 처리하도록 두 Pretendard variant 를 먼저 두고
# 시스템 폰트로 폴백한다.
CONTENT_FONT_STACK = ("'Pretendard Variable', 'Pretendard JP Variable', "
                      "'Malgun Gothic', 'Meiryo', sans-serif")


def font_stack(primary: str) -> str:
    """두 Pretendard variant 를 모두 포함해 한·일 혼용을 처리하는 폴백 체인."""
    primary = primary or "Segoe UI"
    return (f'"{primary}", "Pretendard Variable", "Pretendard JP Variable", '
            f'"Malgun Gothic", "Meiryo", "Segoe UI", sans-serif')


_QSS_TEMPLATE = """
* {{
    font-family: {font_stack};
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

QToolButton[primary="true"], QPushButton[primary="true"] {{
    background: {bg_soft};
    border: 1px solid {border};
    border-radius: 10px;
    padding: 10px 18px;
    color: {text};
    font-size: 13px;
    font-weight: 600;
    min-height: 24px;
    text-align: center;
}}
QToolButton[primary="true"]:hover, QPushButton[primary="true"]:hover {{
    background: {bg_hover};
    border-color: {border_strong};
}}
QToolButton[primary="true"]:pressed, QPushButton[primary="true"]:pressed {{
    background: #E2E2E2;
}}

QToolButton[iconOnly="true"] {{
    background: transparent;
    border: none;
    padding: 4px;
    border-radius: 6px;
}}
QToolButton[iconOnly="true"]:hover {{
    background: rgba(0, 0, 0, 0.06);
}}

QScrollBar:vertical {{
    border: none;
    background: transparent;
    width: 10px;
    margin: 4px 2px 4px 0;
}}
QScrollBar::handle:vertical {{
    background: #D4D4D4;
    border: none;
    border-radius: 5px;
    min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{
    background: #B4B4B4;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    border: none;
    background: none;
    height: 0;
    width: 0;
}}
QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {{
    border: none;
    background: none;
    image: none;
    width: 0;
    height: 0;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
}}
QScrollBar:horizontal {{
    border: none;
    background: transparent;
    height: 10px;
    margin: 0 4px 2px 4px;
}}
QScrollBar::handle:horizontal {{
    background: #D4D4D4;
    border: none;
    border-radius: 5px;
    min-width: 28px;
}}
QScrollBar::handle:horizontal:hover {{
    background: #B4B4B4;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    border: none;
    background: none;
    width: 0;
    height: 0;
}}
QScrollBar::left-arrow:horizontal, QScrollBar::right-arrow:horizontal {{
    border: none;
    background: none;
    image: none;
    width: 0;
    height: 0;
}}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: none;
}}

QListWidget {{
    background: {bg};
    border: none;
    outline: 0;
    padding: 4px;
}}
QListWidget::item {{
    padding: 8px 10px;
    margin: 2px 0;
    border-radius: 8px;
    border: none;
    background: transparent;
    color: {text};
}}
QListWidget::item:hover {{
    background: {bg_hover};
}}
QListWidget::item:selected {{
    background: #1F1F1F;
    color: #FFFFFF;
}}
QListWidget::item:selected:hover {{
    background: #2F2F2F;
}}
/* MainWindow 의 카드 리스트는 항목 자체가 완전 커스텀 위젯이라,
   아이템 레벨 chrome 은 렌더링하지 않는다. objectName 으로 opt-in 한다. */
QListWidget#FlatList::item,
QListWidget#FlatList::item:selected,
QListWidget#FlatList::item:hover {{
    background: transparent;
    color: {text};
    padding: 0;
    margin: 0;
}}

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

QDialogButtonBox QPushButton {{
    min-width: 80px;
}}

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

/* Windows 11 다크 모드 팔레트가 새어 들어오지 않도록 처리한다.
   ``background`` 대신 더 구체적인 ``background-color`` 를 쓰고, 항목은
   명시적으로 transparent 로 둔다. polish 단계에서 QSS 가 Qt 네이티브
   스타일을 이기도록 메뉴 본체의 색과 테두리도 함께 강제 지정한다. */
QMenu {{
    background-color: #FFFFFF;
    border: 1px solid {border};
    border-radius: 8px;
    padding: 4px;
    color: {text};
}}
QMenu::item {{
    background-color: transparent;
    padding: 6px 22px 6px 14px;
    border-radius: 6px;
    color: {text};
    min-width: 130px;
}}
QMenu::item:selected {{
    background-color: {bg_hover};
    color: {text};
}}
QMenu::item:disabled {{
    color: {text_muted};
    background-color: transparent;
}}
QMenu::separator {{
    height: 1px;
    background: {border};
    margin: 4px 6px;
}}
QMenu::right-arrow {{
    width: 10px;
    height: 10px;
}}

QFormLayout > QLabel {{
    color: {text_subtle};
    font-size: 12px;
}}
"""


def build_stylesheet(font_family: str) -> str:
    return _QSS_TEMPLATE.format(
        font_stack=font_stack(font_family),
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
    # QSS 가 덮지 못한 위젯이 Windows 다크 모드 시스템 색으로 폴백하지 않도록
    # 라이트 팔레트를 강제한다. 예: 팝업 QMenu 가 검정 위 검정으로 표시되는 문제.
    pal = app.palette()
    pal.setColor(QPalette.Window, QColor(COLOR_BG))
    pal.setColor(QPalette.Base, QColor(COLOR_BG))
    pal.setColor(QPalette.AlternateBase, QColor(COLOR_BG_SUBTLE))
    pal.setColor(QPalette.WindowText, QColor(COLOR_TEXT))
    pal.setColor(QPalette.Text, QColor(COLOR_TEXT))
    pal.setColor(QPalette.ButtonText, QColor(COLOR_TEXT))
    pal.setColor(QPalette.Button, QColor(COLOR_BG_SOFT))
    pal.setColor(QPalette.ToolTipBase, QColor("#1F1F1F"))
    pal.setColor(QPalette.ToolTipText, QColor("#FFFFFF"))
    pal.setColor(QPalette.Highlight, QColor("#1F1F1F"))
    pal.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    app.setPalette(pal)
    app.setStyleSheet(build_stylesheet(font_family))
    default = QFont(font_family or "Segoe UI", 10)
    app.setFont(default)


def refresh_style(widget) -> None:
    """polish 이후 바뀐 동적 프로퍼티를 셀렉터에 다시 반영한다.

    Qt 는 polish 뒤의 ``setProperty`` 를 자동 재평가하지 않으므로, 스타일에
    영향을 주는 setProperty 호출 뒤에는 이 헬퍼를 거쳐야 한다."""
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
