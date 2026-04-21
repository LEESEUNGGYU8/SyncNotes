from __future__ import annotations

import difflib
from datetime import datetime
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)


def _fmt_ts(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d %H:%M:%S")


def _diff_html(before: str | None, after: str | None) -> str:
    b = (before or "").splitlines(keepends=False)
    a = (after or "").splitlines(keepends=False)
    hd = difflib.HtmlDiff(wrapcolumn=60)
    return hd.make_table(b, a, fromdesc="before", todesc="after", context=False)


class HistoryViewer(QDialog):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("수정 이력")
        self.resize(880, 520)

        self._entries: list[dict[str, Any]] = []
        self._notes: dict[str, dict[str, Any]] = {}  # id -> note dict (for labels)

        top = QHBoxLayout()
        top.addWidget(QLabel("메모:"))
        self._note_combo = QComboBox()
        self._note_combo.addItem("(전체)", userData=None)
        self._note_combo.currentIndexChanged.connect(self._refresh_list)
        top.addWidget(self._note_combo, 1)

        self._list = QListWidget()
        self._list.currentItemChanged.connect(self._on_select)

        self._detail = QTextBrowser()
        self._detail.setOpenExternalLinks(False)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._list)
        splitter.addWidget(self._detail)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        root = QVBoxLayout(self)
        root.addLayout(top)
        root.addWidget(splitter, 1)

    def set_notes(self, notes: list[dict[str, Any]]) -> None:
        self._notes = {n["id"]: n for n in notes}
        current_data = self._note_combo.currentData()
        self._note_combo.blockSignals(True)
        self._note_combo.clear()
        self._note_combo.addItem("(전체)", userData=None)
        for n in notes:
            preview = (n.get("content") or "").splitlines()[:1]
            label = preview[0] if preview else "(빈 메모)"
            label = label[:40] + ("…" if len(label) > 40 else "")
            self._note_combo.addItem(f"{label}  [{n['id'][:8]}]", userData=n["id"])
        # restore selection
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
            action = e.get("action", "")
            user = e.get("user", "")
            ts = _fmt_ts(e.get("session_end", 0))
            nid = (e.get("note_id") or "")[:8]
            item = QListWidgetItem(f"[{ts}] {user} · {action} · {nid}")
            item.setData(Qt.UserRole, e)
            self._list.addItem(item)

    def _on_select(self, current: QListWidgetItem | None, _prev) -> None:
        if current is None:
            self._detail.clear()
            return
        e = current.data(Qt.UserRole)
        html = f"<h3>{e.get('action','').upper()} — {e.get('user','')}</h3>"
        html += f"<p>노트 ID: <code>{e.get('note_id','')}</code></p>"
        html += f"<p>세션: {_fmt_ts(e.get('session_start',0))} → {_fmt_ts(e.get('session_end',0))}</p>"
        cb, ca = e.get("color_before"), e.get("color_after")
        if cb != ca:
            html += (f"<p>배경색: <span style='background:{cb or '#ccc'};"
                     f"padding:0 8px;'>{cb}</span> → "
                     f"<span style='background:{ca or '#ccc'};padding:0 8px;'>{ca}</span></p>")
        html += "<h4>본문 변경</h4>"
        html += _diff_html(e.get("content_before"), e.get("content_after"))
        self._detail.setHtml(html)
