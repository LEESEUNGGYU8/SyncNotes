from __future__ import annotations

import ctypes
import platform
from typing import Any

from PySide6.QtCore import (
    QCoreApplication, QEvent, QPoint, QRect, QSize, Qt, QTimer, Signal,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QIcon,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QShortcut,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
    QTextFormat,
    QTextImageFormat,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QSizeGrip,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from .. import config, i18n
from ..image_export import open_data_url_externally
from ..settings import IMAGE_VIEWER_SYSTEM
from .icons import color_swatch_icon, svg_icon
from .image_viewer import ImageViewerWindow
from .menu_item import add_centered_menu_action
from .rich_text import (
    BULLET_ARROW,
    BULLET_CIRCLE,
    BULLET_CODES,
    BULLET_INFO,
    BULLET_SQUARE,
    CHECKBOX_HEIGHT,
    CHECKBOX_WIDTH,
    MARKER_ARROW,
    MARKER_CHECK0,
    MARKER_CHECK1,
    MARKER_CIRCLE,
    MARKER_CODES,
    MARKER_INFO,
    MARKER_MARGIN,
    MARKER_NONE,
    MARKER_PROP,
    MARKER_SQUARE,
    RichTextEdit,
    bullet_qicon,
    checkbox_qicon,
    marker_code_for_url,
    marker_url_for_code,
)
from .theme import RoundedScrollBar


# 바탕 화면과 앱 창 사이 레이어는 WindowStaysOnTopHint 로 만들 수 없어
# Windows Z-order 최하단에 핀한다.
def _pin_window_to_bottom(hwnd: int) -> None:
    if platform.system() != "Windows" or hwnd == 0:
        return
    HWND_BOTTOM = 1
    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001
    SWP_NOACTIVATE = 0x0010
    try:
        ctypes.windll.user32.SetWindowPos(
            hwnd, HWND_BOTTOM, 0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
        )
    except Exception:
        pass


def _hide_dwm_border(hwnd: int) -> None:
    """Windows 11 이 프레임 없는 창에 덧그리는 DWM 시스템 테두리를 꺼,
    paintEvent 의 둥근 사각형만 경계로 남긴다."""
    if platform.system() != "Windows" or hwnd == 0:
        return
    DWMWA_BORDER_COLOR = 34
    DWMWA_COLOR_NONE = 0xFFFFFFFE
    try:
        dwm = ctypes.WinDLL("dwmapi")
        color = ctypes.c_uint32(DWMWA_COLOR_NONE)
        dwm.DwmSetWindowAttribute(
            hwnd, DWMWA_BORDER_COLOR,
            ctypes.byref(color), ctypes.sizeof(color),
        )
    except Exception:
        pass


def _make_format_button(icon: QIcon, tip: str, checkable: bool = False) -> QToolButton:
    b = QToolButton()
    b.setIcon(icon)
    b.setIconSize(QSize(16, 16))
    b.setToolTip(tip)
    b.setCursor(Qt.PointingHandCursor)
    b.setFocusPolicy(Qt.NoFocus)
    b.setAutoRaise(True)
    b.setCheckable(checkable)
    b.setStyleSheet(
        "QToolButton { border: none; padding: 5px; border-radius: 5px; background: transparent; }"
        "QToolButton:hover { background: rgba(0,0,0,0.08); }"
        "QToolButton:checked { background: rgba(0,0,0,0.14); }"
        "QToolButton::menu-indicator { image: none; }"
    )
    return b


HIGHLIGHT_COLORS = [
    "#FFF59D",
    "#C5E1A5",
    "#B3E5FC",
    "#F8BBD0",
    "#FFCC80",
    "#D1C4E9",
]
DEFAULT_HIGHLIGHT_COLOR = HIGHLIGHT_COLORS[0]

FONT_COLORS = [
    "#1F1F1F",
    "#D64545",
    "#E8830C",
    "#1F8A4C",
    "#1D6FD6",
    "#7A3FCB",
    "#C2185B",
]


def _highlight_swatch_icon(color: str | None, size: int = 18) -> QIcon:
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    rect = QRect(2, 2, size - 4, size - 4)
    if color is None:
        p.setPen(QPen(QColor("#9A9A9A"), 1.2))
        p.setBrush(QColor("#FFFFFF"))
        p.drawRoundedRect(rect, 3, 3)
        p.setPen(QPen(QColor("#D64545"), 1.6))
        p.drawLine(rect.topRight(), rect.bottomLeft())
    else:
        p.setPen(QPen(QColor(0, 0, 0, 60), 1))
        p.setBrush(QColor(color))
        p.drawRoundedRect(rect, 3, 3)
    p.end()
    return QIcon(pix)


def _text_color_for_bg(bg_hex: str) -> str:
    try:
        r = int(bg_hex[1:3], 16)
        g = int(bg_hex[3:5], 16)
        b = int(bg_hex[5:7], 16)
    except (ValueError, IndexError):
        return "#1F1F1F"
    lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
    return "#FFFFFF" if lum < 0.55 else "#1F1F1F"


class StickyNoteWidget(QWidget):
    requestLock = Signal(str)
    releaseLock = Signal(str)
    commitEdit = Signal(str, str, str, int, int, int)  # id, html, color, w, h, version
    deleteRequested = Signal(str)
    hideRequested = Signal(str)
    historyRequested = Signal(str)
    privateToggleRequested = Signal(str, bool)  # note_id, new_private
    positionChanged = Signal(str, int, int)
    sizeChanged = Signal(str, int, int)  # note_id, w, h

    _DEFAULT_FONT_SIZE = 11
    _AUTOSAVE_INTERVAL_MS = 30_000

    def __init__(self, note: dict[str, Any], my_nickname: str,
                 parent: QWidget | None = None,
                 default_font_size: int = 11,
                 settings=None):
        # WindowStaysOnTopHint 대신 showEvent 에서 Z-order 최하단에 핀한다.
        super().__init__(
            parent,
            Qt.FramelessWindowHint | Qt.Tool,
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setMinimumSize(config.MIN_NOTE_WIDTH, config.MIN_NOTE_HEIGHT)

        self.note_id: str = note["id"]
        self.version: int = int(note.get("version", 1))
        self.color: str = note.get("color", config.DEFAULT_COLOR)
        self.private_owner: str | None = note.get("private_owner")
        self._content: str = note.get("content", "") or ""
        self._pending_commit: str | None = None
        self._edit_baseline: tuple[str, str, int, int] | None = None
        self._my_nickname = my_nickname
        self._lock_holder: str | None = None
        self._edit_mode = False
        self._pending_lock = False
        self._first_show_done = False
        # 앱 종료 중 MainWindow 가 설정한다. closeEvent 가 "내 바탕
        # 화면에서 숨기기" 부수 효과를 건너뛰게 한다.
        self._teardown = False
        self._default_font_size = int(default_font_size
                                       or self._DEFAULT_FONT_SIZE)
        # 참조로 보관해 설정 토글이 기존 메모 위젯에 즉시 반영되게 한다.
        self._settings = settings

        root = QVBoxLayout(self)
        # paintEvent 의 둥근 사각형 안쪽(2 px 인셋)에 콘텐츠를 맞춰
        # 핸들 바 버튼이 상단 틴트 스트립에 정확히 가운데 정렬되게 한다.
        root.setContentsMargins(2, 2, 2, 2)
        root.setSpacing(0)

        self._handle = QWidget(self)
        self._handle.setFixedHeight(config.HANDLE_BAR_HEIGHT)
        self._handle.setAttribute(Qt.WA_TranslucentBackground)
        handle_row = QHBoxLayout(self._handle)
        handle_row.setContentsMargins(12, 0, 6, 0)
        handle_row.setSpacing(2)
        handle_row.setAlignment(Qt.AlignVCenter)

        self._private_icon = QLabel(self._handle)
        self._private_icon.setFixedSize(16, 16)
        self._private_icon.setPixmap(
            svg_icon("lock", color="#3A3A3A").pixmap(14, 14))
        self._private_icon.setToolTip(
            i18n.t("sticky.private_icon_tip"))
        self._private_icon.setStyleSheet("background: transparent;")
        self._private_icon.setVisible(bool(self.private_owner))
        handle_row.addWidget(self._private_icon, 0, Qt.AlignVCenter)

        self._lock_label = QLabel("", self._handle)
        self._lock_label.setStyleSheet(
            "color: #3A3A3A; font-size: 11px; background: transparent;"
        )
        handle_row.addWidget(self._lock_label, 1, Qt.AlignVCenter)

        self._color_btn = _make_format_button(
            color_swatch_icon(self.color), i18n.t("sticky.tip_color"))
        self._color_btn.clicked.connect(self._show_color_menu)
        self._history_btn = _make_format_button(
            svg_icon("clock"), i18n.t("sticky.tip_history"))
        self._history_btn.clicked.connect(
            lambda: self.historyRequested.emit(self.note_id))
        self._more_btn = _make_format_button(
            svg_icon("more"), i18n.t("sticky.tip_more"))
        self._more_btn.clicked.connect(self._show_more_menu)
        self._close_btn = _make_format_button(
            svg_icon("close"), i18n.t("sticky.tip_close"))
        self._close_btn.clicked.connect(self._close_sticky)

        for b in (self._color_btn, self._history_btn, self._more_btn, self._close_btn):
            handle_row.addWidget(b, 0, Qt.AlignVCenter)
        root.addWidget(self._handle)

        self._text = RichTextEdit(self)
        self._text.setReadOnly(True)
        self._text.setFrameStyle(QFrame.NoFrame)
        self._text.setAttribute(Qt.WA_TranslucentBackground)
        self._text.viewport().setAutoFillBackground(False)
        self._scrollbar = RoundedScrollBar()
        self._text.setVerticalScrollBar(self._scrollbar)
        self._text.setStyleSheet("QTextEdit { background: transparent; }")
        self._text.setViewportMargins(*config.TEXT_MARGINS)
        default_font = self._text.font()
        default_font.setPointSize(self._default_font_size)
        self._text.setFont(default_font)
        self._text.document().setDefaultFont(default_font)
        self._apply_content_to_view(self._content)
        self._text.viewport().installEventFilter(self)
        self._text.installEventFilter(self)
        self._text.cursorPositionChanged.connect(self._refresh_format_buttons)
        self._text.selectionChanged.connect(self._refresh_format_buttons)
        root.addWidget(self._text, 1)

        self._format_bar = QWidget(self)
        self._format_bar.setFixedHeight(config.FORMAT_BAR_HEIGHT)
        self._format_bar.setAttribute(Qt.WA_TranslucentBackground)
        fb = QHBoxLayout(self._format_bar)
        fb.setContentsMargins(10, 4, 4, 4)
        fb.setSpacing(2)

        self._bold_btn = _make_format_button(
            svg_icon("bold"), i18n.t("sticky.tip_bold"), True)
        self._italic_btn = _make_format_button(
            svg_icon("italic"), i18n.t("sticky.tip_italic"), True)
        self._underline_btn = _make_format_button(
            svg_icon("underline"), i18n.t("sticky.tip_underline"), True)
        self._strike_btn = _make_format_button(
            svg_icon("strike"), i18n.t("sticky.tip_strike"), True)

        self._font_color_btn = _make_format_button(
            svg_icon("text_color"), i18n.t("sticky.tip_font_color"))
        self._font_color_btn.clicked.connect(self._show_font_color_menu)

        self._highlight_btn = _make_format_button(
            svg_icon("highlight"), i18n.t("sticky.tip_highlight"))
        self._highlight_btn.clicked.connect(self._show_highlight_menu)

        self._list_btn = _make_format_button(
            svg_icon("list"), i18n.t("sticky.tip_list"), True)
        self._list_menu = QMenu(self._list_btn)
        add_centered_menu_action(
            self._list_menu, bullet_qicon(BULLET_CIRCLE),
            i18n.t("sticky.menu_circle"),
            lambda: self._apply_bullet_marker(MARKER_CIRCLE))
        add_centered_menu_action(
            self._list_menu, bullet_qicon(BULLET_SQUARE),
            i18n.t("sticky.menu_square"),
            lambda: self._apply_bullet_marker(MARKER_SQUARE))
        add_centered_menu_action(
            self._list_menu, bullet_qicon(BULLET_ARROW),
            i18n.t("sticky.menu_arrow"),
            lambda: self._apply_bullet_marker(MARKER_ARROW))
        add_centered_menu_action(
            self._list_menu, bullet_qicon(BULLET_INFO),
            i18n.t("sticky.menu_info"),
            lambda: self._apply_bullet_marker(MARKER_INFO))
        self._list_menu.addSeparator()
        add_centered_menu_action(
            self._list_menu, checkbox_qicon(False),
            i18n.t("sticky.menu_checkbox"),
            self._apply_checkbox_marker)
        self._list_menu.addSeparator()
        add_centered_menu_action(
            self._list_menu, None, i18n.t("sticky.menu_list_off"),
            self._remove_list_markers)
        self._list_btn.setMenu(self._list_menu)
        self._list_btn.setPopupMode(QToolButton.InstantPopup)

        self._image_btn = _make_format_button(
            svg_icon("image"), i18n.t("sticky.tip_image"))
        self._image_btn.setToolTip(i18n.t("sticky.tip_image_full"))

        self._bold_btn.clicked.connect(self._toggle_bold)
        self._italic_btn.clicked.connect(self._toggle_italic)
        self._underline_btn.clicked.connect(self._toggle_underline)
        self._strike_btn.clicked.connect(self._toggle_strike)
        self._image_btn.clicked.connect(self._attach_image)

        for b in (self._bold_btn, self._italic_btn, self._underline_btn,
                  self._strike_btn, self._font_color_btn, self._highlight_btn,
                  self._list_btn, self._image_btn):
            fb.addWidget(b)
        fb.addStretch(1)

        self._grip = QSizeGrip(self._format_bar)
        self._grip.installEventFilter(self)
        fb.addWidget(self._grip)
        root.addWidget(self._format_bar)

        self._set_format_bar_enabled(False)

        self._shortcuts = [
            QShortcut(QKeySequence.Bold, self, self._toggle_bold),
            QShortcut(QKeySequence.Italic, self, self._toggle_italic),
            QShortcut(QKeySequence.Underline, self, self._toggle_underline),
            QShortcut(QKeySequence("Ctrl+Shift+S"), self, self._toggle_strike),
            QShortcut(QKeySequence("Ctrl+Shift+L"), self, self._toggle_list),
            QShortcut(QKeySequence("Ctrl+Shift+H"), self, self._toggle_highlight),
        ]

        self._overlay = QLabel("", self)
        self._overlay.setAlignment(Qt.AlignCenter)
        self._overlay.setStyleSheet(
            "QLabel { background: rgba(0,0,0,0.45); color: white; "
            "font-size: 13px; border-radius: 6px; }"
        )
        self._overlay.hide()

        self._drag_offset: QPoint | None = None
        # 파일 대화상자가 열리면 창이 비활성화되는데, 그때 changeEvent 가
        # 편집을 조기 커밋해 이후 삽입된 이미지가 세션 밖에서 처리되지
        # 않도록 막는 플래그.
        self._opening_dialog = False
        # 이미지 더블 클릭으로 연 자체 뷰어. 메모당 하나만 두고 재사용한다.
        self._image_viewer: ImageViewerWindow | None = None
        # 더블 클릭의 첫 클릭이 낸 잠금 요청이 아직 응답 전(게스트의 왕복 지연)에
        # 뷰어가 열렸으면, 뒤늦게 온 허용은 편집으로 들어가지 않고 바로 돌려준다.
        self._abandon_grant = False

        # 미완료 편집이 크래시나 강제 종료에서 살아남도록 주기적으로 저장한다.
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(self._AUTOSAVE_INTERVAL_MS)
        self._autosave_timer.timeout.connect(self._autosave_while_editing)

        self.resize(int(note.get("width", config.DEFAULT_NOTE_WIDTH)),
                    int(note.get("height", config.DEFAULT_NOTE_HEIGHT)))

        self._apply_theme_colors()

    def _apply_content_to_view(self, content: str) -> None:
        if not content:
            self._text.clear()
        elif "<" in content and ">" in content:
            self._text.setHtml(content)
        else:
            self._text.setPlainText(content)
        self._convert_loaded_markers()
        # 아직 표시 전이면 뷰포트 폭이 확정되지 않아 fit 이 이미지를 과하게
        # 줄인다. 표시되면 RichTextEdit.resizeEvent 가 알맞은 폭으로 맞춘다.
        if self.isVisible():
            self._text.fit_images_to_viewport()
        # load·fit 을 undo 스택에서 제거해 첫 Ctrl+Z 가 fit 이전
        # 이미지 크기로 되돌아가지 않게 한다.
        self._text.document().clearUndoRedoStacks()

    def _leading_marker(self, block) -> tuple[int, int]:
        """블록 맨 앞에 인라인 마커 이미지가 있으면 ``(code, 제거할 글자수)``
        를 반환한다. 마커 이미지 + 뒤 공백 0~2 개를 함께 센다."""
        it = block.begin()
        if it.atEnd():
            return (MARKER_NONE, 0)
        fmt = it.fragment().charFormat()
        if not fmt.isImageFormat():
            return (MARKER_NONE, 0)
        code = marker_code_for_url(fmt.toImageFormat().name())
        if code == MARKER_NONE:
            return (MARKER_NONE, 0)
        text = block.text()
        length = 1
        while length < 3 and len(text) > length and text[length] == " ":
            length += 1
        return (code, length)

    def _convert_loaded_markers(self) -> None:
        """저장본의 인라인 마커 이미지(+뒤 공백)를 블록 마커 속성으로 바꾼다.
        구버전 인라인 이미지 저장본도 이렇게 현재 모델로 흡수한다."""
        doc = self._text.document()
        positions = []
        block = doc.begin()
        while block.isValid():
            positions.append(block.position())
            block = block.next()
        for pos in reversed(positions):
            code, length = self._leading_marker(doc.findBlock(pos))
            if code == MARKER_NONE:
                continue
            bc = QTextCursor(doc)
            bc.setPosition(pos)
            bc.setPosition(pos + length, QTextCursor.KeepAnchor)
            bc.removeSelectedText()
            self._set_block_marker(doc.findBlock(pos), code)

    def _marker_save_html(self) -> str:
        """블록 마커를 인라인 이미지로 되살린 HTML 을 만든다. 저장 형식은
        예전과 같아(인라인 이미지 + 공백) 호환되고, 다시 불러올 때 블록
        마커로 변환된다. 라이브 문서는 그대로 두고 복제본에서 작업한다."""
        clone = self._text.document().clone()
        positions = []
        block = clone.begin()
        while block.isValid():
            positions.append(
                (block.position(),
                 block.blockFormat().intProperty(MARKER_PROP)))
            block = block.next()
        for pos, code in reversed(positions):
            cur = QTextCursor(clone)
            cur.setPosition(pos)
            # 저장 형식엔 여백 대신 인라인 이미지를 둔다.
            no_margin = QTextBlockFormat()
            no_margin.setLeftMargin(0.0)
            cur.mergeBlockFormat(no_margin)
            if code in MARKER_CODES:
                cur.insertImage(self._make_marker_image_format(code))
                cur.insertText("  ")
        return clone.toHtml()

    def _current_content(self) -> str:
        """서식이 있으면 HTML, 없으면 이력 diff 가독성을 위해 평문을 반환한다.

        '기본과 다른 폰트 크기' 감지가 핵심이다. 그러지 않으면 Ctrl+Wheel
        로 크기만 바꾼 메모가 평문으로 저장돼, 서버 상태에서 다시 렌더할 때
        크기 정보가 사라진다."""
        doc = self._text.document()
        plain = doc.toPlainText()
        default_size = doc.defaultFont().pointSizeF()
        has_rich = False
        block = doc.begin()
        while block.isValid() and not has_rich:
            if self._marker_code(block) in MARKER_CODES:
                has_rich = True
                break
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                if frag.isValid():
                    fmt = frag.charFormat()
                    size = fmt.fontPointSize()
                    if (fmt.fontWeight() > QFont.Normal
                            or fmt.fontItalic()
                            or fmt.fontUnderline()
                            or fmt.fontStrikeOut()
                            or fmt.isImageFormat()
                            or (size > 0
                                and abs(size - default_size) > 0.1)
                            or fmt.hasProperty(QTextFormat.ForegroundBrush)
                            or fmt.hasProperty(QTextFormat.BackgroundBrush)):
                        has_rich = True
                        break
                it += 1
            block = block.next()
        if has_rich:
            return self._marker_save_html()
        return plain

    def apply_server_state(self, note: dict[str, Any]) -> None:
        self.version = int(note.get("version", self.version))
        self.private_owner = note.get("private_owner")
        if hasattr(self, "_private_icon"):
            self._private_icon.setVisible(bool(self.private_owner))
        new_color = note.get("color", self.color)
        if new_color != self.color:
            self.color = new_color
            self._color_btn.setIcon(color_swatch_icon(new_color))
            self._apply_theme_colors()
            self.update()
        new_content = note.get("content", self._content) or ""

        # 방금 전송한 내용이 그대로 돌아온 경우 undo 스택을 지키려고 뷰를 유지한다.
        own_echo = (self._pending_commit is not None
                    and new_content == self._pending_commit)
        if own_echo:
            self._pending_commit = None
            self._content = new_content
        elif not self._edit_mode and new_content != self._content:
            self._content = new_content
            self._apply_content_to_view(new_content)
        else:
            self._content = new_content

        w = int(note.get("width", self.width()))
        h = int(note.get("height", self.height()))
        if (w, h) != (self.width(), self.height()) and not self._edit_mode:
            self.resize(w, h)

    def set_lock_holder(self, holder: str | None) -> None:
        self._lock_holder = holder
        self._refresh_lock_ui()

    def is_locked_by_other(self) -> bool:
        return self._lock_holder is not None and self._lock_holder != self._my_nickname

    def enter_edit_mode(self) -> None:
        self._pending_lock = False
        if self._abandon_grant:
            # 이미지 뷰어를 여는 사이에 허용이 도착했다. 변경 없이 잠금만 돌려주므로
            # 서버는 이력 행을 남기지 않는다(변경 없는 편집 종료와 같은 경로).
            self._abandon_grant = False
            self.releaseLock.emit(self.note_id)
            return
        self._edit_mode = True
        self._text.setReadOnly(False)
        self._text.setFocus(Qt.OtherFocusReason)
        self._overlay.hide()
        self._lock_label.setText(i18n.t("sticky.lock_editing_self"))
        self._set_format_bar_enabled(True)
        self._refresh_format_buttons()
        self._autosave_timer.start()
        # 변화 없는 focus→blur 가 updated_at 을 건드리거나 no-op 이력
        # 행을 남기지 않도록 비교 기준 스냅샷을 떠 둔다.
        self._edit_baseline = self._edit_snapshot()

    def _edit_snapshot(self) -> tuple[str, str, int, int]:
        return (self._current_content(), self.color,
                self.width(), self.height())

    def show_lock_denied(self, holder: str) -> None:
        self._pending_lock = False
        self._abandon_grant = False
        self._text.setReadOnly(True)
        self._lock_label.setText(i18n.t("sticky.lock_editing_by", holder=holder))
        self._show_overlay(i18n.t("sticky.lock_overlay", holder=holder))

    def _close_sticky(self) -> None:
        if self._edit_mode:
            self._commit_and_release()
        self.hideRequested.emit(self.note_id)

    def _set_format_bar_enabled(self, enabled: bool) -> None:
        for b in (self._bold_btn, self._italic_btn, self._underline_btn,
                  self._strike_btn, self._font_color_btn, self._highlight_btn,
                  self._list_btn, self._image_btn):
            b.setEnabled(enabled)

    def _refresh_lock_ui(self) -> None:
        if self._edit_mode:
            return
        if self._lock_holder is None:
            self._lock_label.setText("")
            self._overlay.hide()
            self._text.setReadOnly(True)
            self._set_format_bar_enabled(False)
        elif self._lock_holder == self._my_nickname:
            self._lock_label.setText(i18n.t("sticky.lock_editing_self"))
        else:
            self._lock_label.setText(
                i18n.t("sticky.lock_editing_by", holder=self._lock_holder))
            self._show_overlay(
                i18n.t("sticky.lock_overlay", holder=self._lock_holder))
            self._set_format_bar_enabled(False)

    def _show_overlay(self, text: str) -> None:
        self._overlay.setText(text)
        self._reposition_overlay()
        self._overlay.show()
        self._overlay.raise_()

    def _reposition_overlay(self) -> None:
        m = 12
        self._overlay.setGeometry(
            m,
            config.HANDLE_BAR_HEIGHT + m,
            self.width() - 2 * m,
            self.height() - config.HANDLE_BAR_HEIGHT - config.FORMAT_BAR_HEIGHT - 2 * m,
        )

    def _request_edit(self) -> None:
        if self._edit_mode or self._pending_lock:
            # 뷰어를 연 뒤 응답이 오기 전에 다시 눌렀다면 편집하려는 뜻이다.
            self._abandon_grant = False
            return
        if self._lock_holder and self._lock_holder != self._my_nickname:
            return
        self._pending_lock = True
        self.requestLock.emit(self.note_id)

    def _commit_and_release(self) -> None:
        if not self._edit_mode:
            return
        self._autosave_timer.stop()
        self._edit_mode = False
        self._text.setReadOnly(True)
        snapshot = self._edit_snapshot()
        # baseline 과 같으면 updated_at·이력 행을 건드리지 않도록 전송을 건너뛴다.
        if snapshot != self._edit_baseline:
            new_content = snapshot[0]
            self._pending_commit = new_content
            self._content = new_content
            self.commitEdit.emit(
                self.note_id, new_content, self.color,
                self.width(), self.height(), self.version,
            )
        self._edit_baseline = None
        self.releaseLock.emit(self.note_id)
        self._lock_label.setText("")
        self._set_format_bar_enabled(False)

    def _autosave_while_editing(self) -> None:
        """잠금을 유지한 채 flush 하되, baseline 이후 변화가 없으면 no-op
        이라 손대지 않은 편집기가 updated_at 을 올리지 않는다."""
        if not self._edit_mode:
            return
        snapshot = self._edit_snapshot()
        if snapshot == self._edit_baseline:
            return
        new_content = snapshot[0]
        self._pending_commit = new_content
        self._content = new_content
        self.commitEdit.emit(
            self.note_id, new_content, self.color,
            self.width(), self.height(), self.version,
        )
        # baseline 을 굴려 이후 idle 자동 저장 tick 도 no-op 이 되게 한다.
        self._edit_baseline = snapshot

    def flush_pending_edit(self) -> None:
        """앱 종료 전 메인 창이 호출해 저장되지 않은 편집을 잃지 않게 한다."""
        if self._edit_mode:
            self._commit_and_release()

    def _show_color_menu(self) -> None:
        if not self._edit_mode:
            self._request_edit()
            return
        menu = QMenu(self)
        container = QWidget(menu)
        grid = QGridLayout(container)
        grid.setContentsMargins(6, 6, 6, 6)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        for index, hex_color in enumerate(config.COLORS):
            r, c = divmod(index, 4)
            btn = QToolButton(container)
            btn.setFixedSize(28, 28)
            btn.setIcon(color_swatch_icon(hex_color, 22))
            btn.setIconSize(QSize(22, 22))
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFocusPolicy(Qt.NoFocus)
            btn.setToolTip(hex_color)
            btn.setStyleSheet(
                "QToolButton { border: none; padding: 2px; border-radius: 6px; background: transparent; }"
                "QToolButton:hover { background: rgba(0,0,0,0.08); }"
            )
            btn.clicked.connect(
                lambda _checked=False, c=hex_color, m=menu: (self._set_color(c), m.close()))
            grid.addWidget(btn, r, c)
        action = QWidgetAction(menu)
        action.setDefaultWidget(container)
        menu.addAction(action)
        menu.exec(self._color_btn.mapToGlobal(QPoint(0, self._color_btn.height())))

    def _show_highlight_menu(self) -> None:
        if not self._edit_mode:
            self._request_edit()
            return
        menu = QMenu(self)
        container = QWidget(menu)
        outer = QVBoxLayout(container)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(4)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        for index, hex_color in enumerate(HIGHLIGHT_COLORS):
            r, c = divmod(index, 3)
            btn = QToolButton(container)
            btn.setFixedSize(28, 28)
            btn.setIcon(_highlight_swatch_icon(hex_color, 22))
            btn.setIconSize(QSize(22, 22))
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFocusPolicy(Qt.NoFocus)
            btn.setStyleSheet(
                "QToolButton { border: none; padding: 2px; "
                "border-radius: 6px; background: transparent; }"
                "QToolButton:hover { background: rgba(0,0,0,0.08); }"
            )
            btn.clicked.connect(
                lambda _checked=False, c=hex_color, m=menu:
                    (self._apply_highlight(c), m.close()))
            grid.addWidget(btn, r, c)
        outer.addLayout(grid)

        divider = QFrame(container)
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet("color: rgba(0,0,0,0.08);")
        outer.addWidget(divider)

        clear_btn = QToolButton(container)
        clear_btn.setText(i18n.t("sticky.bg_none"))
        clear_btn.setIcon(_highlight_swatch_icon(None, 18))
        clear_btn.setIconSize(QSize(18, 18))
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.setFocusPolicy(Qt.NoFocus)
        clear_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        clear_btn.setFixedHeight(26)
        clear_btn.setStyleSheet(
            "QToolButton { border: none; padding: 2px 6px; "
            "border-radius: 6px; background: transparent; "
            "color: #1F1F1F; font-size: 12px; text-align: left; }"
            "QToolButton:hover { background: rgba(0,0,0,0.08); }"
        )
        clear_btn.clicked.connect(
            lambda _checked=False, m=menu:
                (self._apply_highlight(None), m.close()))
        outer.addWidget(clear_btn)

        action = QWidgetAction(menu)
        action.setDefaultWidget(container)
        menu.addAction(action)
        menu.exec(self._highlight_btn.mapToGlobal(
            QPoint(0, self._highlight_btn.height())))

    def _show_more_menu(self) -> None:
        is_private = bool(self.private_owner)
        menu = QMenu(self)
        # 전역 QSS 가 팝업 단위에서 Win11 다크 팔레트를 항상 이기지는
        # 못해 light 스타일을 명시한다.
        menu.setStyleSheet(
            "QMenu { background-color: #FFFFFF; "
            "border: 1px solid #EAEAEA; border-radius: 8px; "
            "padding: 4px; color: #1F1F1F; }"
            "QMenu::item { background-color: transparent; "
            "padding: 6px 22px 6px 14px; border-radius: 6px; "
            "color: #1F1F1F; min-width: 160px; }"
            "QMenu::item:selected { background-color: #F0F0F0; "
            "color: #1F1F1F; }"
            "QMenu::separator { height: 1px; background: #EAEAEA; "
            "margin: 4px 6px; }"
        )
        act_hide = menu.addAction(i18n.t("sticky.more_hide"))
        act_hide.triggered.connect(lambda: self.hideRequested.emit(self.note_id))
        act_hist = menu.addAction(i18n.t("sticky.tip_history"))
        act_hist.triggered.connect(
            lambda: self.historyRequested.emit(self.note_id))
        menu.addSeparator()
        act_priv = menu.addAction(
            i18n.t("sticky.more_private_off") if is_private
            else i18n.t("sticky.more_private_on"))
        act_priv.triggered.connect(
            lambda: self.privateToggleRequested.emit(
                self.note_id, not is_private))
        menu.addSeparator()
        act_del = menu.addAction(i18n.t("sticky.more_delete"))
        act_del.triggered.connect(
            lambda: self.deleteRequested.emit(self.note_id))
        menu.exec(self._more_btn.mapToGlobal(QPoint(0, self._more_btn.height())))

    def _set_color(self, color: str) -> None:
        self.color = color
        self._color_btn.setIcon(color_swatch_icon(color))
        self._apply_theme_colors()
        self.update()

    def _apply_theme_colors(self) -> None:
        """어두운 색 메모에서도 글리프가 보이도록 전경을 배경에 맞춰 다시 칠한다."""
        fg = _text_color_for_bg(self.color)
        self._text.setStyleSheet(
            f"QTextEdit {{ background: transparent; color: {fg}; }}")
        # 메모 배경색이 제각각이라 스크롤바 핸들 색을 배경 대비에 맞춘다.
        if fg == "#FFFFFF":
            self._scrollbar.set_colors(QColor(255, 255, 255, 90),
                                       QColor(255, 255, 255, 140))
        else:
            self._scrollbar.set_colors(QColor(0, 0, 0, 60),
                                       QColor(0, 0, 0, 105))
        lock_color = "#E5E5E5" if fg == "#FFFFFF" else "#3A3A3A"
        self._lock_label.setStyleSheet(
            f"color: {lock_color}; font-size: 11px; background: transparent;")
        self._history_btn.setIcon(svg_icon("clock", color=fg))
        self._more_btn.setIcon(svg_icon("more", color=fg))
        self._close_btn.setIcon(svg_icon("close", color=fg))
        self._bold_btn.setIcon(svg_icon("bold", color=fg))
        self._italic_btn.setIcon(svg_icon("italic", color=fg))
        self._underline_btn.setIcon(svg_icon("underline", color=fg))
        self._strike_btn.setIcon(svg_icon("strike", color=fg))
        self._font_color_btn.setIcon(svg_icon("text_color", color=fg))
        self._highlight_btn.setIcon(svg_icon("highlight", color=fg))
        self._list_btn.setIcon(svg_icon("list", color=fg))
        self._image_btn.setIcon(svg_icon("image", color=fg))

    def _merge_char_format(self, fmt: QTextCharFormat) -> None:
        cursor = self._text.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.WordUnderCursor)
        cursor.mergeCharFormat(fmt)
        self._text.mergeCurrentCharFormat(fmt)

    def _toggle_bold(self) -> None:
        if not self._edit_mode:
            return
        current_weight = self._text.fontWeight()
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Normal if current_weight > QFont.Normal else QFont.Bold)
        self._merge_char_format(fmt)
        self._refresh_format_buttons()

    def _toggle_italic(self) -> None:
        if not self._edit_mode:
            return
        fmt = QTextCharFormat()
        fmt.setFontItalic(not self._text.fontItalic())
        self._merge_char_format(fmt)
        self._refresh_format_buttons()

    def _toggle_underline(self) -> None:
        if not self._edit_mode:
            return
        fmt = QTextCharFormat()
        fmt.setFontUnderline(not self._text.fontUnderline())
        self._merge_char_format(fmt)
        self._refresh_format_buttons()

    def _toggle_strike(self) -> None:
        if not self._edit_mode:
            return
        current = self._text.currentCharFormat()
        fmt = QTextCharFormat()
        fmt.setFontStrikeOut(not current.fontStrikeOut())
        self._merge_char_format(fmt)
        self._refresh_format_buttons()

    def _apply_highlight(self, color: str | None) -> None:
        """``None`` 은 no-brush 배경을 설정해 강조를 지운다. Qt 는 저장
        HTML 에서 이를 통째로 생략한다."""
        if not self._edit_mode:
            return
        fmt = QTextCharFormat()
        if color is None:
            fmt.setBackground(QBrush(Qt.NoBrush))
        else:
            fmt.setBackground(QBrush(QColor(color)))
        self._merge_char_format(fmt)
        self._refresh_format_buttons()

    def _toggle_highlight(self) -> None:
        if not self._edit_mode:
            return
        current = self._text.currentCharFormat()
        bg = current.background()
        already_highlighted = (
            bg.style() != Qt.NoBrush
            and bg.color().alpha() > 0
            and bg.color() != QColor(self.color)
        )
        self._apply_highlight(None if already_highlighted
                              else DEFAULT_HIGHLIGHT_COLOR)

    def _show_font_color_menu(self) -> None:
        if not self._edit_mode:
            self._request_edit()
            return
        menu = QMenu(self)
        container = QWidget(menu)
        outer = QVBoxLayout(container)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(4)
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        for index, hex_color in enumerate(FONT_COLORS):
            r, c = divmod(index, 4)
            btn = QToolButton(container)
            btn.setFixedSize(28, 28)
            btn.setIcon(color_swatch_icon(hex_color, 22))
            btn.setIconSize(QSize(22, 22))
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFocusPolicy(Qt.NoFocus)
            btn.setStyleSheet(
                "QToolButton { border: none; padding: 2px; "
                "border-radius: 6px; background: transparent; }"
                "QToolButton:hover { background: rgba(0,0,0,0.08); }")
            btn.clicked.connect(
                lambda _checked=False, c=hex_color, m=menu:
                    (self._apply_font_color(c), m.close()))
            grid.addWidget(btn, r, c)
        outer.addLayout(grid)

        divider = QFrame(container)
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet("color: rgba(0,0,0,0.08);")
        outer.addWidget(divider)

        default_btn = QToolButton(container)
        default_btn.setText(i18n.t("sticky.font_color_default"))
        default_btn.setIcon(color_swatch_icon(_text_color_for_bg(self.color), 18))
        default_btn.setIconSize(QSize(18, 18))
        default_btn.setCursor(Qt.PointingHandCursor)
        default_btn.setFocusPolicy(Qt.NoFocus)
        default_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        default_btn.setFixedHeight(26)
        default_btn.setStyleSheet(
            "QToolButton { border: none; padding: 2px 6px; "
            "border-radius: 6px; background: transparent; "
            "color: #1F1F1F; font-size: 12px; text-align: left; }"
            "QToolButton:hover { background: rgba(0,0,0,0.08); }")
        default_btn.clicked.connect(
            lambda _checked=False, m=menu:
                (self._apply_font_color(None), m.close()))
        outer.addWidget(default_btn)

        action = QWidgetAction(menu)
        action.setDefaultWidget(container)
        menu.addAction(action)
        menu.exec(self._font_color_btn.mapToGlobal(
            QPoint(0, self._font_color_btn.height())))

    def _apply_font_color(self, color: str | None) -> None:
        if not self._edit_mode:
            return
        fmt = QTextCharFormat()
        if color is None:
            fmt.setForeground(QBrush(QColor(_text_color_for_bg(self.color))))
        else:
            fmt.setForeground(QBrush(QColor(color)))
        self._merge_char_format(fmt)
        self._refresh_format_buttons()

    def _toggle_list(self) -> None:
        if not self._edit_mode:
            return
        self._apply_bullet_marker(MARKER_CIRCLE)

    def _marker_code(self, block) -> int:
        return block.blockFormat().intProperty(MARKER_PROP)

    def _set_block_marker(self, block, code: int) -> None:
        """블록 마커를 설정/해제한다. 마커가 있으면 본문을 마커 폭만큼 들여
        paintEvent 가 여백에 글리프를 그릴 자리를 비운다. 블록 포맷에 두므로
        undo 로 되돌릴 수 있고, 줄 분할 시 여백과 함께 상속돼 리스트가
        자연히 이어진다."""
        if not block.isValid():
            return
        new_bf = QTextBlockFormat()
        if code in MARKER_CODES:
            new_bf.setProperty(MARKER_PROP, code)
            new_bf.setLeftMargin(MARKER_MARGIN)
        else:
            new_bf.setProperty(MARKER_PROP, MARKER_NONE)
            new_bf.setLeftMargin(0.0)
        QTextCursor(block).mergeBlockFormat(new_bf)
        self._text.viewport().update()

    def _strip_block_marker(self, block) -> None:
        self._set_block_marker(block, MARKER_NONE)

    def _make_marker_image_format(self, code: int) -> QTextImageFormat:
        fmt = QTextImageFormat()
        fmt.setName(marker_url_for_code(code) or "")
        fmt.setWidth(float(CHECKBOX_WIDTH))
        fmt.setHeight(float(CHECKBOX_HEIGHT))
        fmt.setVerticalAlignment(QTextCharFormat.AlignMiddle)
        return fmt

    def _selected_block_positions(self) -> list[int]:
        cursor = self._text.textCursor()
        doc = self._text.document()
        start_block = doc.findBlock(cursor.selectionStart())
        end_block = doc.findBlock(cursor.selectionEnd())
        positions = []
        block = start_block
        while block.isValid():
            positions.append(block.position())
            if block.position() >= end_block.position():
                break
            block = block.next()
        return positions

    def _apply_marker_to_selection(self, code: int, *,
                                    is_member) -> None:
        doc = self._text.document()
        positions = self._selected_block_positions()
        if not positions:
            return
        all_same = all(is_member(self._marker_code(doc.findBlock(pos)))
                       for pos in positions)
        target = MARKER_NONE if all_same else code
        cursor = self._text.textCursor()
        cursor.beginEditBlock()
        try:
            for pos in positions:
                self._set_block_marker(doc.findBlock(pos), target)
        finally:
            cursor.endEditBlock()
        self._refresh_format_buttons()

    def _apply_bullet_marker(self, code: int) -> None:
        """선택한 줄이 모두 같은 글머리면 제거하고, 아니면 설정한다."""
        if not self._edit_mode or code not in BULLET_CODES:
            return
        self._apply_marker_to_selection(code, is_member=lambda c: c == code)

    def _apply_checkbox_marker(self) -> None:
        """선택한 줄이 모두 체크박스면 제거하고, 아니면 설정한다."""
        if not self._edit_mode:
            return
        self._apply_marker_to_selection(
            MARKER_CHECK0,
            is_member=lambda c: c in (MARKER_CHECK0, MARKER_CHECK1))

    def _remove_list_markers(self) -> None:
        if not self._edit_mode:
            return
        doc = self._text.document()
        positions = self._selected_block_positions()
        cursor = self._text.textCursor()
        cursor.beginEditBlock()
        try:
            for pos in positions:
                self._set_block_marker(doc.findBlock(pos), MARKER_NONE)
        finally:
            cursor.endEditBlock()
        self._refresh_format_buttons()

    def _try_toggle_checkbox_at(self, pos: QPoint) -> bool:
        """체크박스 줄의 왼쪽 여백(마커 영역)을 클릭하면 토글하고 True 를
        반환한다."""
        if not self._edit_mode:
            return False
        block = self._text.cursorForPosition(pos).block()
        code = self._marker_code(block)
        if code not in (MARKER_CHECK0, MARKER_CHECK1):
            return False
        start = QTextCursor(block)
        start.setPosition(block.position())
        if pos.x() >= self._text.cursorRect(start).left():
            return False
        will_check = code == MARKER_CHECK0
        new_code = MARKER_CHECK1 if will_check else MARKER_CHECK0
        doc = self._text.document()
        bc = QTextCursor(doc)
        # Ctrl+Z 가 토글과 이동을 함께 되돌리도록 한 undo 단계로 묶는다.
        bc.beginEditBlock()
        try:
            self._set_block_marker(block, new_code)
            if will_check and self._move_checked_to_bottom_enabled():
                self._move_block_to_end(doc.findBlock(block.position()))
        finally:
            bc.endEditBlock()
        return True

    def _move_checked_to_bottom_enabled(self) -> bool:
        s = self._settings
        return bool(s is not None and getattr(s, "move_checked_to_bottom", False))

    def _move_block_to_end(self, block) -> None:
        """``block`` 이 이미 마지막이면 no-op."""
        doc = self._text.document()
        if not block.isValid() or not block.next().isValid():
            return
        code = self._marker_code(block)
        snap = QTextCursor(doc)
        snap.setPosition(block.position())
        snap.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
        fragment = snap.selection()
        # 뒤따르는 블록 구분자까지 제거해야 원래 위치에 빈 줄이 남지 않는다.
        cut = QTextCursor(doc)
        cut.setPosition(block.position())
        cut.setPosition(block.position() + block.length(),
                        QTextCursor.KeepAnchor)
        cut.removeSelectedText()
        end = QTextCursor(doc)
        end.movePosition(QTextCursor.End)
        end.insertBlock()
        end.insertFragment(fragment)
        self._set_block_marker(end.block(), code)
        # 다음 키 입력이 방금 체크한 줄의 편집을 이어가도록 커서를 옮긴다.
        self._text.setTextCursor(end)

    def _refresh_format_buttons(self) -> None:
        if not self._edit_mode:
            return
        current = self._text.currentCharFormat()
        self._bold_btn.setChecked(current.fontWeight() > QFont.Normal)
        self._italic_btn.setChecked(current.fontItalic())
        self._underline_btn.setChecked(current.fontUnderline())
        self._strike_btn.setChecked(current.fontStrikeOut())
        self._list_btn.setChecked(
            self._marker_code(self._text.textCursor().block()) in MARKER_CODES)

    def _attach_image(self) -> None:
        if not self._edit_mode:
            self._request_edit()
            return
        self._opening_dialog = True
        try:
            path, _ = QFileDialog.getOpenFileName(
                self, i18n.t("sticky.img_dialog_title"), "",
                i18n.t("sticky.img_filter"))
            if path:
                self._text.setFocus(Qt.OtherFocusReason)
                # QImage 경로는 첫 프레임만 캡처하므로, 애니메이션 보존을
                # 위해 경로 기반 inserter 로 라우팅한다.
                self._text._insert_image_from_path(path)
        finally:
            # 네이티브 대화상자가 닫히며 늦게 전달되는 비활성화 이벤트까지
            # 가드가 살아 있도록 이벤트 루프를 한 번 돌린 뒤 해제한다.
            QTimer.singleShot(0, self._end_opening_dialog)

    def _end_opening_dialog(self) -> None:
        self._opening_dialog = False

    def eventFilter(self, obj, event) -> bool:
        if obj is self._grip and event.type() == QEvent.MouseButtonRelease:
            self.sizeChanged.emit(self.note_id, self.width(), self.height())
        # 본문 이미지 더블 클릭은 보기/편집 상태와 무관하게 뷰어를 연다.
        # 첫 클릭이 편집 요청을 냈더라도 뷰어 창이 초점을 가져가면 changeEvent
        # 가 편집을 커밋하고 잠금을 풀어 메모는 곧 보기 상태로 돌아간다.
        if (obj is self._text.viewport()
                and event.type() == QEvent.MouseButtonDblClick
                and event.button() == Qt.LeftButton):
            hit = self._text.content_image_at(event.pos())
            if hit is not None:
                url, ordinal = hit
                self._open_image_viewer(url, ordinal)
                event.accept()
                return True
        if obj is self._text.viewport() and event.type() == QEvent.MouseButtonPress:
            if not self._edit_mode:
                self._request_edit()
                return True
            if event.button() == Qt.LeftButton:
                if self._try_toggle_checkbox_at(event.pos()):
                    event.accept()
                    return True
        if obj is self._text and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Escape and self._edit_mode:
                self._commit_and_release()
                return True
            # Shift/Ctrl+Enter 는 자동 글머리 없이 soft break·명시적
            # 커밋을 할 수 있도록 기본 동작에 맡긴다.
            if (event.key() in (Qt.Key_Return, Qt.Key_Enter)
                    and self._edit_mode
                    and not (event.modifiers() &
                              (Qt.ShiftModifier | Qt.ControlModifier))):
                if self._handle_marker_enter():
                    return True
        return super().eventFilter(obj, event)

    def _open_image_viewer(self, url: str, ordinal: int) -> None:
        """설정에 따라 OS 기본 뷰어(임시 파일 경유) 또는 자체 뷰어로 연다.
        OS 뷰어를 열지 못하면 자체 뷰어로 물러선다."""
        # 뷰어(외부 앱 포함)가 초점을 가져가면 어차피 changeEvent 가 편집을
        # 커밋하지만, 활성화 순서에 기대지 않고 여기서 먼저 끝내 잠금을 오래
        # 붙들지 않는다. 변경이 없으면 서버에 아무것도 보내지 않는다.
        if self._edit_mode:
            self._commit_and_release()
        elif self._pending_lock:
            self._abandon_grant = True
        mode = (getattr(self._settings, "image_viewer", "")
                if self._settings is not None else "")
        if mode == IMAGE_VIEWER_SYSTEM and open_data_url_externally(url):
            return
        urls = self._text.content_image_urls()
        if not urls:
            urls = [url]
        if not (0 <= ordinal < len(urls)) or urls[ordinal] != url:
            ordinal = urls.index(url) if url in urls else 0
        viewer = self._image_viewer
        if viewer is None:
            viewer = ImageViewerWindow()
            viewer.destroyed.connect(self._on_image_viewer_destroyed)
            # 메모가 삭제·재구성되어 파괴되면 그 이미지를 보던 창도 닫는다.
            self.destroyed.connect(viewer.close)
            self._image_viewer = viewer
        viewer.set_images(urls, ordinal)
        viewer.present(self.screen())

    def _on_image_viewer_destroyed(self, *_args) -> None:
        self._image_viewer = None

    def _handle_marker_enter(self) -> bool:
        """마커만 있는 빈 줄에서 Enter 면 마커를 없애 리스트를 끝낸다.
        체크박스는 다음 줄을 '미체크'로 잇는다. 글머리는 기본 Enter 가 새 블록
        에 마커 서식을 상속해 자연히 이어지므로 False 를 돌려준다."""
        cursor = self._text.textCursor()
        if cursor.hasSelection():
            return False
        block = cursor.block()
        code = self._marker_code(block)
        if code not in MARKER_CODES:
            return False
        if not block.text().strip():
            self._set_block_marker(block, MARKER_NONE)
            self._refresh_format_buttons()
            return True
        if code in (MARKER_CHECK0, MARKER_CHECK1):
            cursor.beginEditBlock()
            try:
                cursor.insertBlock()
                self._set_block_marker(cursor.block(), MARKER_CHECK0)
            finally:
                cursor.endEditBlock()
            self._text.setTextCursor(cursor)
            self._refresh_format_buttons()
            return True
        return False

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton and self._on_handle_bar(event.pos()):
            self._drag_offset = (event.globalPosition().toPoint()
                                  - self.frameGeometry().topLeft())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and (event.buttons() & Qt.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None:
            self._drag_offset = None
            self.positionChanged.emit(self.note_id, self.x(), self.y())
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _on_handle_bar(self, pos: QPoint) -> bool:
        return self._handle.geometry().contains(pos)

    def changeEvent(self, event) -> None:
        if (event.type() == QEvent.ActivationChange
                and self._edit_mode and not self.isActiveWindow()
                and not self._opening_dialog):
            self._commit_and_release()
        super().changeEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._reposition_overlay()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        hwnd = int(self.winId())
        if not self._first_show_done:
            self._first_show_done = True
            _hide_dwm_border(hwnd)
        _pin_window_to_bottom(hwnd)

    def closeEvent(self, event) -> None:
        # 종료 중에는 hideRequested 를 emit 하지 않는다. emit 하면 로컬
        # 'hidden' 플래그가 켜져 다음 실행 시 메모가 숨겨진 채 뜬다.
        # closingDown() 은 aboutToQuit 의 teardown 보다 closeEvent 가
        # 먼저 오는 Windows 세션 종료 경로의 안전망이다.
        if self._teardown or QCoreApplication.closingDown():
            event.accept()
            return
        if self._edit_mode:
            self._commit_and_release()
        self.hideRequested.emit(self.note_id)
        event.ignore()
        self.hide()

    # 핸들 바를 메모 색의 옅은 톤으로 칠해 두 영역 경계에 선이 보이지 않게 한다.
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(self.color))
        painter.drawRoundedRect(rect, config.CORNER_RADIUS, config.CORNER_RADIUS)
        bar = QColor(self.color)
        h, s, v, a = bar.getHsv()
        v = min(255, v + 18)
        s = max(0, s - 20)
        bar.setHsv(h, s, v, a)
        hb = QRect(rect.x(), rect.y(), rect.width(), config.HANDLE_BAR_HEIGHT)
        path = QPainterPath()
        path.addRoundedRect(hb, config.CORNER_RADIUS, config.CORNER_RADIUS)
        painter.fillPath(path, bar)
        painter.end()
