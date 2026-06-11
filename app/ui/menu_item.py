from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QWidget,
    QWidgetAction,
)


class CenteredMenuItem(QWidget):
    """아이콘을 고정 폭 칼럼에 가운데 정렬해, 아이콘 유무와 무관하게 텍스트
    들여쓰기를 일정하게 유지한다."""

    activated = Signal()

    ICON_COL_WIDTH = 40
    ROW_HEIGHT = 30
    ICON_SIZE = 16

    def __init__(self, icon: QIcon | None, text: str, *,
                 enabled: bool = True, parent: QWidget | None = None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_Hover, True)
        self.setMouseTracking(True)
        self.setFixedHeight(self.ROW_HEIGHT)
        self.setCursor(Qt.PointingHandCursor if enabled else Qt.ArrowCursor)

        row = QHBoxLayout(self)
        row.setContentsMargins(4, 0, 18, 0)
        row.setSpacing(0)

        icon_lbl = QLabel(self)
        icon_lbl.setFixedWidth(self.ICON_COL_WIDTH)
        icon_lbl.setAlignment(Qt.AlignCenter)
        if icon is not None and not icon.isNull():
            icon_lbl.setPixmap(icon.pixmap(self.ICON_SIZE, self.ICON_SIZE))
        row.addWidget(icon_lbl)

        self._text_lbl = QLabel(text, self)
        self._text_lbl.setStyleSheet(
            "color: #1F1F1F; font-size: 13px; background: transparent;"
            if enabled else
            "color: #A0A0A0; font-size: 13px; background: transparent;"
        )
        row.addWidget(self._text_lbl, 1)

        self._hover = False
        self._enabled = enabled

    def enterEvent(self, event) -> None:  # noqa: N802
        if self._enabled:
            self._hover = True
            self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if (self._enabled
                and event.button() == Qt.LeftButton
                and self.rect().contains(event.pos())):
            self.activated.emit()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        if not self._hover:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#F0F0F0"))
        p.drawRoundedRect(self.rect().adjusted(2, 1, -2, -1), 5, 5)


def add_centered_menu_action(menu: QMenu, icon: QIcon | None, text: str,
                              handler=None, *,
                              enabled: bool = True) -> QWidgetAction:
    widget = CenteredMenuItem(icon, text, enabled=enabled)
    action = QWidgetAction(menu)
    action.setDefaultWidget(widget)
    action.setEnabled(enabled)
    if enabled and handler is not None:
        widget.activated.connect(handler)
        widget.activated.connect(menu.close)
    menu.addAction(action)
    return action
