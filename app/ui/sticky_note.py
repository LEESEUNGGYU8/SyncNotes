from __future__ import annotations

from typing import Any

from PySide6.QtCore import QEvent, QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QSizeGrip,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import config
from .icons import color_swatch_icon, svg_icon


class StickyNoteWidget(QWidget):
    requestLock = Signal(str)                         # note_id
    releaseLock = Signal(str)                         # note_id
    commitEdit = Signal(str, str, str, int, int, int)  # id, content, color, w, h, version
    deleteRequested = Signal(str)
    hideRequested = Signal(str)
    historyRequested = Signal(str)
    positionChanged = Signal(str, int, int)

    def __init__(self, note: dict[str, Any], my_nickname: str,
                 parent: QWidget | None = None):
        super().__init__(
            parent,
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool,
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setMinimumSize(config.MIN_NOTE_WIDTH, config.MIN_NOTE_HEIGHT)

        self.note_id: str = note["id"]
        self.version: int = int(note.get("version", 1))
        self.color: str = note.get("color", config.DEFAULT_COLOR)
        self._content: str = note.get("content", "")
        self._my_nickname = my_nickname
        self._lock_holder: str | None = None  # None = free; else holder name
        self._edit_mode = False
        self._pending_lock = False

        # --- layout ---
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)  # room for drop shadow
        root.setSpacing(0)

        # handle bar
        self._handle = QWidget(self)
        self._handle.setFixedHeight(config.HANDLE_BAR_HEIGHT)
        self._handle.setAttribute(Qt.WA_TranslucentBackground)
        handle_row = QHBoxLayout(self._handle)
        handle_row.setContentsMargins(10, 2, 6, 2)
        handle_row.setSpacing(4)

        self._lock_label = QLabel("", self._handle)
        self._lock_label.setStyleSheet("color: #444; font-size: 11px;")
        handle_row.addWidget(self._lock_label, 1)

        self._color_btn = self._mk_tool_btn(
            color_swatch_icon(self.color), "배경색 변경", self._show_color_menu)
        self._hide_btn = self._mk_tool_btn(
            svg_icon("eye_off"), "이 메모 숨기기",
            lambda: self.hideRequested.emit(self.note_id))
        self._history_btn = self._mk_tool_btn(
            svg_icon("clock"), "수정 이력",
            lambda: self.historyRequested.emit(self.note_id))
        self._delete_btn = self._mk_tool_btn(
            svg_icon("close"), "삭제",
            lambda: self.deleteRequested.emit(self.note_id))
        for b in (self._color_btn, self._history_btn, self._hide_btn, self._delete_btn):
            handle_row.addWidget(b)

        root.addWidget(self._handle)

        # text area
        self._text = QTextEdit(self)
        self._text.setReadOnly(True)
        self._text.setPlainText(self._content)
        self._text.setFrameStyle(QFrame.NoFrame)
        self._text.setAttribute(Qt.WA_TranslucentBackground)
        self._text.viewport().setAutoFillBackground(False)
        self._text.setStyleSheet(
            "QTextEdit { background: transparent; color: #222; }"
        )
        self._text.setViewportMargins(*config.TEXT_MARGINS)
        font = QFont()
        font.setPointSize(11)
        self._text.setFont(font)
        self._text.viewport().installEventFilter(self)
        self._text.installEventFilter(self)
        root.addWidget(self._text, 1)

        # resize grip
        grip_row = QHBoxLayout()
        grip_row.setContentsMargins(0, 0, 2, 2)
        grip_row.addStretch(1)
        self._grip = QSizeGrip(self)
        grip_row.addWidget(self._grip)
        root.addLayout(grip_row)

        # overlay for "other is editing"
        self._overlay = QLabel("", self)
        self._overlay.setAlignment(Qt.AlignCenter)
        self._overlay.setStyleSheet(
            "QLabel { background: rgba(0,0,0,0.45); color: white; "
            "font-size: 13px; border-radius: 6px; }"
        )
        self._overlay.hide()

        # drag state
        self._drag_offset: QPoint | None = None

        self.resize(int(note.get("width", config.DEFAULT_NOTE_WIDTH)),
                    int(note.get("height", config.DEFAULT_NOTE_HEIGHT)))

    # ---- builders ----
    def _mk_tool_btn(self, icon: QIcon, tip: str, cb) -> QToolButton:
        b = QToolButton(self._handle)
        b.setIcon(icon)
        b.setIconSize(QSize(16, 16))
        b.setToolTip(tip)
        b.setCursor(Qt.PointingHandCursor)
        b.setFocusPolicy(Qt.NoFocus)
        b.setAutoRaise(True)
        b.setStyleSheet(
            "QToolButton { border: none; padding: 3px 6px; }"
            "QToolButton:hover { background: rgba(0,0,0,0.08); border-radius: 4px; }"
        )
        b.clicked.connect(cb)
        return b

    # ---- public API used by MainWindow ----
    def apply_server_state(self, note: dict[str, Any]) -> None:
        """Apply a note_updated from the server. Do NOT clobber text while
        the user is actively editing (we hold the lock)."""
        self.version = int(note.get("version", self.version))
        new_color = note.get("color", self.color)
        if new_color != self.color:
            self.color = new_color
            self._color_btn.setIcon(color_swatch_icon(new_color))
            self.update()
        new_content = note.get("content", self._content)
        if not self._edit_mode and new_content != self._text.toPlainText():
            self._content = new_content
            self._text.setPlainText(new_content)
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
        self._edit_mode = True
        self._text.setReadOnly(False)
        self._text.setFocus(Qt.OtherFocusReason)
        self._overlay.hide()
        self._lock_label.setText("편집 중 (나)")

    def show_lock_denied(self, holder: str) -> None:
        self._pending_lock = False
        self._text.setReadOnly(True)
        self._lock_label.setText(f"{holder}님이 편집 중")
        self._show_overlay(f"{holder}님이 편집 중입니다")

    # ---- internal ----
    def _refresh_lock_ui(self) -> None:
        if self._edit_mode:
            return
        if self._lock_holder is None:
            self._lock_label.setText("")
            self._overlay.hide()
            self._text.setReadOnly(True)
        elif self._lock_holder == self._my_nickname:
            self._lock_label.setText("편집 중 (나)")
        else:
            self._lock_label.setText(f"{self._lock_holder}님이 편집 중")
            self._show_overlay(f"{self._lock_holder}님이 편집 중입니다")

    def _show_overlay(self, text: str) -> None:
        self._overlay.setText(text)
        self._reposition_overlay()
        self._overlay.show()
        self._overlay.raise_()

    def _reposition_overlay(self) -> None:
        m = 12
        self._overlay.setGeometry(
            m, config.HANDLE_BAR_HEIGHT + m,
            self.width() - 2 * m,
            self.height() - config.HANDLE_BAR_HEIGHT - 2 * m,
        )

    def _request_edit(self) -> None:
        if self._edit_mode or self._pending_lock:
            return
        if self._lock_holder and self._lock_holder != self._my_nickname:
            # ignore — already locked by other
            return
        self._pending_lock = True
        self.requestLock.emit(self.note_id)

    def _commit_and_release(self) -> None:
        if not self._edit_mode:
            return
        self._edit_mode = False
        self._text.setReadOnly(True)
        new_content = self._text.toPlainText()
        self.commitEdit.emit(
            self.note_id, new_content, self.color,
            self.width(), self.height(), self.version,
        )
        self._content = new_content
        self.releaseLock.emit(self.note_id)
        self._lock_label.setText("")

    def _show_color_menu(self) -> None:
        if not self._edit_mode:
            self._request_edit()
            return  # after lock granted, user can click again
        menu = QMenu(self)
        for hex_color in config.COLORS:
            act = menu.addAction(hex_color)
            act.triggered.connect(lambda _=False, c=hex_color: self._set_color(c))
        menu.exec(self._color_btn.mapToGlobal(QPoint(0, self._color_btn.height())))

    def _set_color(self, color: str) -> None:
        self.color = color
        self._color_btn.setIcon(color_swatch_icon(color))
        self.update()

    # ---- events ----
    def eventFilter(self, obj, event) -> bool:
        if obj is self._text.viewport() and event.type() == QEvent.MouseButtonPress:
            if not self._edit_mode:
                self._request_edit()
                return True
        if obj is self._text and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Escape and self._edit_mode:
                self._commit_and_release()
                return True
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton and self._on_handle_bar(event.pos()):
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
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

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)

    def changeEvent(self, event) -> None:
        # Commit when the widget window itself loses activation
        if event.type() == QEvent.ActivationChange and self._edit_mode and not self.isActiveWindow():
            self._commit_and_release()
        super().changeEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._reposition_overlay()

    def moveEvent(self, event) -> None:
        super().moveEvent(event)

    def closeEvent(self, event) -> None:
        # Treat window close as 'hide for me only'
        self.hideRequested.emit(self.note_id)
        event.ignore()
        self.hide()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(3, 3, -3, -3)
        # drop shadow
        shadow = QColor(0, 0, 0, 50)
        for i in range(4):
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, 12 - i * 2))
            painter.drawRoundedRect(rect.adjusted(i, i, i, i),
                                     config.CORNER_RADIUS, config.CORNER_RADIUS)
        # body
        painter.setPen(QPen(QColor(0, 0, 0, 30), 1))
        painter.setBrush(QColor(self.color))
        painter.drawRoundedRect(rect, config.CORNER_RADIUS, config.CORNER_RADIUS)
        # handle bar slight tint
        hb = QRect(rect.x(), rect.y(), rect.width(), config.HANDLE_BAR_HEIGHT)
        path = QPainterPath()
        path.addRoundedRect(hb, config.CORNER_RADIUS, config.CORNER_RADIUS)
        painter.fillPath(path, QColor(0, 0, 0, 18))
        # separator
        painter.setPen(QColor(0, 0, 0, 35))
        y = rect.y() + config.HANDLE_BAR_HEIGHT
        painter.drawLine(rect.x() + 6, y, rect.right() - 6, y)
        painter.end()
