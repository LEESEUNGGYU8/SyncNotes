from __future__ import annotations

import difflib
import html
from datetime import datetime
from typing import Any

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStyle,
    QStyledItemDelegate,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .. import datetime_fmt, i18n
from . import theme
from .rich_text import html_to_plain


_ACTION_COLOR = {
    "create": ("#E6F5EC", "#15803D"),
    "update": ("#E6EEFB", "#1D4ED8"),
    "delete": ("#FCE3E7", "#B0122C"),
}


def _action_label(action: str) -> str:
    return i18n.t(f"history.action_{action}") if action in _ACTION_COLOR else action


def _fmt_ts(ms: int) -> str:
    if not ms:
        return ""
    return datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d %H:%M:%S")


def _fmt_relative(ms: int) -> str:
    return datetime_fmt.fmt_relative(ms)


def _render_inline_diff(before: str | None, after: str | None) -> str:
    a = html_to_plain(before or "")
    b = html_to_plain(after or "")
    if a == b:
        return ('<div style="color:#8A8A8A; font-style:italic;">'
                + i18n.t("history.no_body_change") + '</div>')

    def tok(s: str) -> list[str]:
        out: list[str] = []
        buf = ""
        for ch in s:
            if ch.isalnum():
                buf += ch
            else:
                if buf:
                    out.append(buf)
                    buf = ""
                out.append(ch)
        if buf:
            out.append(buf)
        return out

    a_toks = tok(a)
    b_toks = tok(b)
    sm = difflib.SequenceMatcher(None, a_toks, b_toks, autojunk=False)
    parts: list[str] = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            parts.append(html.escape("".join(a_toks[i1:i2]))
                          .replace("\n", "<br/>"))
        elif op == "delete":
            seg = html.escape("".join(a_toks[i1:i2])).replace("\n", "<br/>")
            parts.append(
                f'<span style="background:#FFE0E4; color:#8A0014; '
                f'text-decoration:line-through; border-radius:3px; padding:0 2px;">{seg}</span>')
        elif op == "insert":
            seg = html.escape("".join(b_toks[j1:j2])).replace("\n", "<br/>")
            parts.append(
                f'<span style="background:#DFF5E1; color:#0E5E2B; '
                f'border-radius:3px; padding:0 2px;">{seg}</span>')
        elif op == "replace":
            del_seg = html.escape("".join(a_toks[i1:i2])).replace("\n", "<br/>")
            ins_seg = html.escape("".join(b_toks[j1:j2])).replace("\n", "<br/>")
            parts.append(
                f'<span style="background:#FFE0E4; color:#8A0014; '
                f'text-decoration:line-through; border-radius:3px; padding:0 2px;">{del_seg}</span>'
                f'<span style="background:#DFF5E1; color:#0E5E2B; '
                f'border-radius:3px; padding:0 2px;">{ins_seg}</span>')
    return (f'<div style="font-family: {theme.CONTENT_FONT_STACK}; '
            'font-size: 13px; line-height: 1.7; color:#1F1F1F; '
            'white-space: pre-wrap;">' + "".join(parts) + "</div>")


class _HistoryItemDelegate(QStyledItemDelegate):
    """선택·호버 배경을 직접 그린다. 그렇지 않으면 기본 배경이 행 요소를 가린다."""

    ROW_HEIGHT = 62

    def sizeHint(self, option, index) -> QSize:
        return QSize(0, self.ROW_HEIGHT)

    def paint(self, painter: QPainter, option, index) -> None:
        entry = index.data(Qt.UserRole)
        if not entry:
            super().paint(painter, option, index)
            return

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
        is_hover = bool(option.state & QStyle.StateFlag.State_MouseOver)

        rect = option.rect.adjusted(6, 3, -6, -3)

        if is_selected:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#1F1F1F"))
            painter.drawRoundedRect(rect, 9, 9)
        elif is_hover:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#F1F1F1"))
            painter.drawRoundedRect(rect, 9, 9)

        action = entry.get("action", "")
        bg, fg = _ACTION_COLOR.get(action, ("#ECECEC", "#555555"))
        label = _action_label(action)

        badge_w = 42
        badge_rect = QRect(rect.x() + 10, rect.y() + 10, badge_w, 20)
        painter.setBrush(QColor(bg))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(badge_rect, 6, 6)
        font_badge = QFont(option.font)
        font_badge.setBold(True)
        font_badge.setPointSizeF(9.0)
        painter.setFont(font_badge)
        painter.setPen(QColor(fg))
        painter.drawText(badge_rect, Qt.AlignCenter, label)

        font_user = QFont(option.font)
        font_user.setBold(True)
        font_user.setPointSizeF(10.5)
        painter.setFont(font_user)
        painter.setPen(QColor("#FFFFFF" if is_selected else "#1F1F1F"))
        user_x = badge_rect.right() + 10
        user_rect = QRect(user_x, rect.y() + 10, rect.right() - user_x - 8, 22)
        painter.drawText(user_rect, Qt.AlignVCenter | Qt.AlignLeft,
                         entry.get("user", ""))

        font_ts = QFont(option.font)
        font_ts.setPointSizeF(9.5)
        painter.setFont(font_ts)
        painter.setPen(QColor("#B4B4B4" if is_selected else "#6B6B6B"))
        ts_rect = QRect(rect.x() + 12, rect.y() + 34, rect.width() - 20, 18)
        painter.drawText(ts_rect, Qt.AlignVCenter | Qt.AlignLeft,
                         _fmt_relative(entry.get("session_end", 0)))

        painter.restore()


class HistoryViewer(QDialog):
    # (note_id, content_after)
    restoreRequested = Signal(str, str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(i18n.t("history.window_title"))
        self.resize(940, 580)
        self.setMinimumSize(740, 420)

        self._entries: list[dict[str, Any]] = []
        self._notes: dict[str, dict[str, Any]] = {}
        self._current_entry: dict[str, Any] | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        top = QHBoxLayout()
        lbl = QLabel(i18n.t("history.filter_label"))
        lbl.setStyleSheet(
            "color:#6B6B6B; font-size: 12px; font-weight: 600;")
        top.addWidget(lbl)
        self._note_combo = QComboBox()
        self._note_combo.addItem(i18n.t("history.all"), userData=None)
        self._note_combo.currentIndexChanged.connect(self._refresh_list)
        top.addWidget(self._note_combo, 1)
        root.addLayout(top)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(10)

        left = QFrame()
        left.setFrameShape(QFrame.NoFrame)
        left_v = QVBoxLayout(left)
        left_v.setContentsMargins(0, 0, 0, 0)
        left_v.setSpacing(0)
        self._list = QListWidget()
        self._list.setItemDelegate(_HistoryItemDelegate(self._list))
        self._list.setVerticalScrollBar(theme.RoundedScrollBar())
        self._list.setMouseTracking(True)
        self._list.setUniformItemSizes(True)
        self._list.currentItemChanged.connect(self._on_select)
        self._list.setStyleSheet(
            "QListWidget { background:#FFFFFF; border:1px solid #EAEAEA; "
            "border-radius: 10px; padding: 4px; }"
            "QListWidget::item { padding: 0; margin: 0; background: transparent; }"
            "QListWidget::item:selected { background: transparent; color: #1F1F1F; }"
            "QListWidget::item:hover { background: transparent; }"
        )
        left_v.addWidget(self._list)
        splitter.addWidget(left)

        right = QFrame()
        right.setFrameShape(QFrame.NoFrame)
        right_v = QVBoxLayout(right)
        right_v.setContentsMargins(16, 0, 0, 0)
        right_v.setSpacing(10)

        self._header = QLabel(i18n.t("history.select_prompt"))
        self._header.setStyleSheet(
            "font-size: 16px; font-weight: 700; color: #1F1F1F;")
        right_v.addWidget(self._header)

        self._meta = QLabel("")
        self._meta.setStyleSheet("color:#6B6B6B; font-size: 12px;")
        self._meta.setWordWrap(True)
        self._meta.setTextFormat(Qt.RichText)
        right_v.addWidget(self._meta)

        self._color_row = QLabel("")
        self._color_row.setStyleSheet("font-size: 12px;")
        self._color_row.setTextFormat(Qt.RichText)
        self._color_row.setVisible(False)
        right_v.addWidget(self._color_row)

        section = QLabel(i18n.t("history.section_body"))
        section.setProperty("role", "sectionHeader")
        section.setStyleSheet("font-size: 12px; font-weight: 700; color:#1F1F1F; margin-top: 4px;")
        right_v.addWidget(section)

        self._detail = QTextBrowser()
        self._detail.setOpenExternalLinks(False)
        self._detail.setStyleSheet(
            "QTextBrowser { background:#FAFAFA; border:1px solid #EAEAEA; "
            "border-radius: 10px; padding: 12px; font-size: 13px; "
            f"font-family: {theme.CONTENT_FONT_STACK}; }}"
        )
        right_v.addWidget(self._detail, 1)

        restore_row = QHBoxLayout()
        restore_row.addStretch(1)
        self._restore_btn = QPushButton(i18n.t("history.btn_restore"))
        self._restore_btn.setCursor(Qt.PointingHandCursor)
        self._restore_btn.setProperty("secondary", True)
        self._restore_btn.setEnabled(False)
        self._restore_btn.clicked.connect(self._on_restore_clicked)
        restore_row.addWidget(self._restore_btn)
        right_v.addLayout(restore_row)

        splitter.addWidget(right)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([300, 620])
        root.addWidget(splitter, 1)

    def set_notes(self, notes: list[dict[str, Any]]) -> None:
        self._notes = {n["id"]: n for n in notes}
        current_data = self._note_combo.currentData()
        self._note_combo.blockSignals(True)
        self._note_combo.clear()
        self._note_combo.addItem(i18n.t("history.all"), userData=None)
        for n in notes:
            preview = html_to_plain(n.get("content") or "").splitlines()[:1]
            label = preview[0] if preview else i18n.t("history.empty_note")
            label = label[:40] + ("…" if len(label) > 40 else "")
            self._note_combo.addItem(f"{label}  ·  {n['id'][:8]}", userData=n["id"])
        idx = self._note_combo.findData(current_data)
        if idx < 0:
            idx = 0
        self._note_combo.setCurrentIndex(idx)
        self._note_combo.blockSignals(False)
        self._refresh_list()

    def set_entries(self, entries: list[dict[str, Any]]) -> None:
        self._entries = sorted(entries, key=lambda e: e.get("session_end", 0),
                               reverse=True)
        self._refresh_list()

    def append_entry(self, entry: dict[str, Any]) -> None:
        self._entries.insert(0, entry)
        self._refresh_list()

    def _current_note_filter(self) -> str | None:
        return self._note_combo.currentData()

    def _refresh_list(self) -> None:
        self._list.clear()
        note_id = self._current_note_filter()
        for e in self._entries:
            if note_id is not None and e.get("note_id") != note_id:
                continue
            item = QListWidgetItem()
            item.setData(Qt.UserRole, e)
            self._list.addItem(item)

    def _on_select(self, current: QListWidgetItem | None, _prev) -> None:
        if current is None:
            self._header.setText(i18n.t("history.select_prompt"))
            self._meta.setText("")
            self._color_row.setVisible(False)
            self._detail.clear()
            self._current_entry = None
            self._restore_btn.setEnabled(False)
            self._restore_btn.setToolTip("")
            return
        e = current.data(Qt.UserRole)
        self._current_entry = e
        action = e.get("action", "")
        label = _action_label(action)
        self._header.setText(f"{label}  —  {e.get('user', '')}")
        start = _fmt_ts(e.get("session_start", 0))
        end = _fmt_ts(e.get("session_end", 0))
        note_short = (e.get("note_id") or "")[:8]
        self._meta.setText(
            i18n.t("history.meta", id=note_short, start=start, end=end)
        )
        cb, ca = e.get("color_before"), e.get("color_after")
        if cb != ca and (cb or ca):
            self._color_row.setText(
                i18n.t("history.color_change") + " "
                f"<span style='display:inline-block; background:{cb or '#ccc'}; "
                f"padding: 0 10px; border-radius:3px;'>&nbsp;</span> "
                f"<b>→</b> "
                f"<span style='display:inline-block; background:{ca or '#ccc'}; "
                f"padding: 0 10px; border-radius:3px;'>&nbsp;</span>"
            )
            self._color_row.setVisible(True)
        else:
            self._color_row.setVisible(False)
        self._detail.setHtml(
            _render_inline_diff(e.get("content_before"), e.get("content_after")))

        # 내용을 알고 메모가 아직 존재할 때만 복원할 수 있다. 서버가 soft-delete
        # 된 메모의 업데이트를 거부하므로 'delete' 항목은 복원 불가다.
        note_id = e.get("note_id")
        can_restore = (
            action != "delete"
            and e.get("content_after") is not None
            and note_id in self._notes
        )
        self._restore_btn.setEnabled(can_restore)
        if can_restore:
            self._restore_btn.setToolTip(
                i18n.t("history.tip_restore"))
        elif action == "delete":
            self._restore_btn.setToolTip(
                i18n.t("history.tip_delete"))
        elif note_id not in self._notes:
            self._restore_btn.setToolTip(
                i18n.t("history.tip_gone"))
        else:
            self._restore_btn.setToolTip(
                i18n.t("history.tip_no_content"))

    def _on_restore_clicked(self) -> None:
        e = self._current_entry
        if e is None:
            return
        note_id = e.get("note_id")
        content = e.get("content_after")
        if not note_id or content is None:
            return
        when = _fmt_ts(e.get("session_end", 0))
        user = e.get("user") or ""
        reply = QMessageBox.question(
            self,
            i18n.t("history.confirm_title"),
            i18n.t("history.confirm_body", when=when, user=user),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self.restoreRequested.emit(note_id, content)
