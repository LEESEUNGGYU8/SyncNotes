from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import config
from ..local_state import LocalStateStore
from ..network.client_base import ClientBase
from .history_viewer import HistoryViewer
from .icons import svg_icon
from .sticky_note import StickyNoteWidget


class MainWindow(QMainWindow):
    def __init__(self, client: ClientBase, local_state: LocalStateStore,
                 role: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"ClaudeNotes - {role} ({client.nickname()})")
        self.resize(380, 520)

        self._client = client
        self._local = local_state
        self._role = role
        self._notes: dict[str, dict[str, Any]] = {}
        self._locks: dict[str, str] = {}
        self._stickies: dict[str, StickyNoteWidget] = {}
        self._users: list[str] = []

        self._build_ui()
        self._wire_client()

    # ---- build ----
    def _build_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)

        # toolbar: create note (with color menu), history
        toolbar = QToolBar()
        toolbar.setIconSize(toolbar.iconSize())
        self.addToolBar(toolbar)

        new_btn = QToolButton()
        new_btn.setIcon(svg_icon("plus"))
        new_btn.setText("새 메모")
        new_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        new_btn.setPopupMode(QToolButton.MenuButtonPopup)
        menu = QMenu(new_btn)
        for c in config.COLORS:
            act = menu.addAction(c)
            act.triggered.connect(lambda _=False, color=c: self._create_note(color))
        new_btn.setMenu(menu)
        new_btn.clicked.connect(lambda: self._create_note(config.DEFAULT_COLOR))
        toolbar.addWidget(new_btn)

        history_btn = QToolButton()
        history_btn.setIcon(svg_icon("clock"))
        history_btn.setText("이력")
        history_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        history_btn.clicked.connect(self._open_history)
        toolbar.addWidget(history_btn)

        toolbar.addSeparator()

        self._users_label = QLabel("접속: -")
        toolbar.addWidget(self._users_label)

        # list of notes
        root.addWidget(QLabel("메모 목록 (체크 = 바탕화면에 표시)"))
        self._list = QListWidget()
        self._list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_list_menu)
        self._list.itemDoubleClicked.connect(self._on_item_double_clicked)
        root.addWidget(self._list, 1)

        status = QStatusBar()
        self.setStatusBar(status)
        self._status = status
        self._status.showMessage("접속 중...")

        self._history_viewer: HistoryViewer | None = None

    def _wire_client(self) -> None:
        c = self._client
        c.welcomed.connect(self._on_welcomed)
        c.noteCreated.connect(self._on_note_created)
        c.noteUpdated.connect(self._on_note_updated)
        c.noteDeleted.connect(self._on_note_deleted)
        c.lockGranted.connect(self._on_lock_granted)
        c.lockDenied.connect(self._on_lock_denied)
        c.lockHeld.connect(self._on_lock_held)
        c.lockReleased.connect(self._on_lock_released)
        c.userJoined.connect(self._on_user_joined)
        c.userLeft.connect(self._on_user_left)
        c.historyAppended.connect(self._on_history_appended)
        c.historyList.connect(self._on_history_list)
        c.connectionChanged.connect(self._on_connection_changed)
        c.errorOccurred.connect(self._on_error)

    # ---- client actions ----
    def _create_note(self, color: str) -> None:
        self._client.create_note(color,
                                  config.DEFAULT_NOTE_WIDTH,
                                  config.DEFAULT_NOTE_HEIGHT)

    def _open_history(self) -> None:
        if self._history_viewer is None:
            self._history_viewer = HistoryViewer(self)
        self._history_viewer.set_notes(list(self._notes.values()))
        self._history_viewer.show()
        self._history_viewer.raise_()
        self._client.get_history(None)

    # ---- signal handlers ----
    def _on_connection_changed(self, connected: bool) -> None:
        if connected:
            self._status.showMessage("연결됨")
        else:
            self._status.showMessage("연결 끊김 — 재연결 시도 중…")

    def _on_error(self, message: str) -> None:
        self._status.showMessage(f"오류: {message}", 5000)

    def _on_welcomed(self, data: dict) -> None:
        self._status.showMessage(
            f"연결됨 — 주기 {data.get('heartbeat_ms', 0)}ms", 5000)
        self._users = list(data.get("users", []))
        self._refresh_users_label()
        # replace all notes
        for w in list(self._stickies.values()):
            w.close()
            w.deleteLater()
        self._stickies.clear()
        self._notes.clear()
        self._locks = dict(data.get("locks", {}))
        for note in data.get("notes", []):
            self._notes[note["id"]] = note
        self._rebuild_list()
        for note in self._notes.values():
            self._ensure_sticky(note)

    def _on_note_created(self, note: dict) -> None:
        self._notes[note["id"]] = note
        self._append_list_item(note)
        # initialize local state as visible
        st = self._local.state.get_note_state(note["id"])
        st.hidden = False
        self._local.save()
        self._ensure_sticky(note)

    def _on_note_updated(self, note: dict) -> None:
        self._notes[note["id"]] = note
        self._update_list_item(note)
        w = self._stickies.get(note["id"])
        if w is not None:
            w.apply_server_state(note)

    def _on_note_deleted(self, note_id: str) -> None:
        self._notes.pop(note_id, None)
        self._remove_list_item(note_id)
        w = self._stickies.pop(note_id, None)
        if w is not None:
            w.close()
            w.deleteLater()
        self._local.state.remove_note(note_id)
        self._local.save()

    def _on_lock_granted(self, note_id: str) -> None:
        self._locks[note_id] = self._client.nickname()
        w = self._stickies.get(note_id)
        if w is not None:
            w.enter_edit_mode()

    def _on_lock_denied(self, note_id: str, holder: str) -> None:
        w = self._stickies.get(note_id)
        if w is not None:
            w.show_lock_denied(holder or "다른 사용자")

    def _on_lock_held(self, note_id: str, holder: str) -> None:
        self._locks[note_id] = holder
        w = self._stickies.get(note_id)
        if w is not None:
            w.set_lock_holder(holder)

    def _on_lock_released(self, note_id: str) -> None:
        self._locks.pop(note_id, None)
        w = self._stickies.get(note_id)
        if w is not None:
            w.set_lock_holder(None)

    def _on_user_joined(self, nickname: str) -> None:
        if nickname not in self._users:
            self._users.append(nickname)
        self._refresh_users_label()
        self._status.showMessage(f"{nickname} 접속", 3000)

    def _on_user_left(self, nickname: str) -> None:
        if nickname in self._users:
            self._users.remove(nickname)
        self._refresh_users_label()
        self._status.showMessage(f"{nickname} 퇴장", 3000)

    def _on_history_appended(self, entry: dict) -> None:
        if self._history_viewer is not None and self._history_viewer.isVisible():
            self._history_viewer.append_entry(entry)

    def _on_history_list(self, _note_id: str, entries: list) -> None:
        if self._history_viewer is not None:
            self._history_viewer.set_entries(entries)

    # ---- list rendering ----
    def _rebuild_list(self) -> None:
        self._list.clear()
        for note in self._notes.values():
            self._append_list_item(note)

    def _list_row_for(self, note_id: str) -> int:
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.data(Qt.UserRole) == note_id:
                return i
        return -1

    def _append_list_item(self, note: dict) -> None:
        item = QListWidgetItem()
        item.setData(Qt.UserRole, note["id"])
        self._list.addItem(item)
        self._bind_row_widget(item, note)

    def _update_list_item(self, note: dict) -> None:
        row = self._list_row_for(note["id"])
        if row < 0:
            self._append_list_item(note)
            return
        item = self._list.item(row)
        w = self._list.itemWidget(item)
        if isinstance(w, _NoteRow):
            w.update_from(note)

    def _remove_list_item(self, note_id: str) -> None:
        row = self._list_row_for(note_id)
        if row >= 0:
            self._list.takeItem(row)

    def _bind_row_widget(self, item: QListWidgetItem, note: dict) -> None:
        row = _NoteRow(
            note=note,
            visible=not self._local.state.get_note_state(note["id"]).hidden,
            on_visibility=lambda nid, vis: self._set_note_visibility(nid, vis),
        )
        item.setSizeHint(row.sizeHint())
        self._list.setItemWidget(item, row)

    def _on_list_menu(self, pos: QPoint) -> None:
        item = self._list.itemAt(pos)
        if item is None:
            return
        note_id = item.data(Qt.UserRole)
        menu = QMenu(self)
        act_del = menu.addAction("삭제")
        act_del.triggered.connect(lambda: self._delete_note_confirm(note_id))
        menu.exec(self._list.viewport().mapToGlobal(pos))

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        note_id = item.data(Qt.UserRole)
        self._set_note_visibility(note_id, True)
        w = self._stickies.get(note_id)
        if w is not None:
            w.raise_()
            w.activateWindow()

    def _delete_note_confirm(self, note_id: str) -> None:
        reply = QMessageBox.question(self, "삭제 확인",
                                      "이 메모를 삭제하시겠습니까?")
        if reply == QMessageBox.Yes:
            self._client.delete_note(note_id)

    # ---- sticky widgets ----
    def _ensure_sticky(self, note: dict) -> None:
        note_id = note["id"]
        if note_id in self._stickies:
            w = self._stickies[note_id]
            w.apply_server_state(note)
        else:
            w = StickyNoteWidget(note, self._client.nickname())
            w.requestLock.connect(self._client.acquire_lock)
            w.releaseLock.connect(self._client.release_lock)
            w.commitEdit.connect(self._on_commit_edit)
            w.deleteRequested.connect(self._delete_note_confirm)
            w.hideRequested.connect(lambda nid: self._set_note_visibility(nid, False))
            w.historyRequested.connect(self._open_history_for)
            w.positionChanged.connect(self._on_position_changed)
            self._stickies[note_id] = w

        st = self._local.state.get_note_state(note_id)
        w.move(st.x, st.y)
        holder = self._locks.get(note_id)
        if holder and holder != self._client.nickname():
            w.set_lock_holder(holder)
        else:
            w.set_lock_holder(None)
        if not st.hidden:
            w.show()
        else:
            w.hide()

    def _on_commit_edit(self, note_id: str, content: str, color: str,
                        w: int, h: int, version: int) -> None:
        self._client.update_note(note_id, content, color, w, h, version)

    def _on_position_changed(self, note_id: str, x: int, y: int) -> None:
        self._local.state.set_note_state(note_id, x=x, y=y)
        self._local.save()

    def _set_note_visibility(self, note_id: str, visible: bool) -> None:
        self._local.state.set_note_state(note_id, hidden=not visible)
        self._local.save()
        w = self._stickies.get(note_id)
        if w is not None:
            if visible:
                w.show()
                w.raise_()
            else:
                w.hide()
        # update list row checkbox
        row = self._list_row_for(note_id)
        if row >= 0:
            item = self._list.item(row)
            rw = self._list.itemWidget(item)
            if isinstance(rw, _NoteRow):
                rw.set_visible_checked(visible)

    def _open_history_for(self, note_id: str) -> None:
        if self._history_viewer is None:
            self._history_viewer = HistoryViewer(self)
        self._history_viewer.set_notes(list(self._notes.values()))
        # pre-select this note
        idx = self._history_viewer._note_combo.findData(note_id)
        if idx >= 0:
            self._history_viewer._note_combo.setCurrentIndex(idx)
        self._history_viewer.show()
        self._history_viewer.raise_()
        self._client.get_history(None)

    # ---- misc ----
    def _refresh_users_label(self) -> None:
        if self._users:
            self._users_label.setText("접속: " + ", ".join(self._users))
        else:
            self._users_label.setText("접속: -")

    def closeEvent(self, event) -> None:
        for w in self._stickies.values():
            w.close()
            w.deleteLater()
        self._client.stop()
        super().closeEvent(event)


class _NoteRow(QWidget):
    def __init__(self, note: dict, visible: bool, on_visibility):
        super().__init__()
        self._on_visibility = on_visibility
        self._note_id = note["id"]

        self._check = QCheckBox()
        self._check.setChecked(visible)
        self._check.toggled.connect(
            lambda v: self._on_visibility(self._note_id, v))

        self._swatch = QLabel()
        self._swatch.setFixedSize(14, 14)

        self._label = QLabel()
        self._label.setWordWrap(True)

        row = QHBoxLayout(self)
        row.setContentsMargins(4, 2, 4, 2)
        row.addWidget(self._check)
        row.addWidget(self._swatch)
        row.addWidget(self._label, 1)

        self.update_from(note)

    def update_from(self, note: dict) -> None:
        color = note.get("color", "#cccccc")
        self._swatch.setStyleSheet(
            f"background:{color}; border:1px solid rgba(0,0,0,0.2); border-radius:3px;"
        )
        preview = (note.get("content") or "").splitlines()[:1]
        text = preview[0] if preview else "(빈 메모)"
        if len(text) > 60:
            text = text[:60] + "…"
        meta = f"  · {note.get('updated_by','')}"
        self._label.setText(text + meta)

    def set_visible_checked(self, checked: bool) -> None:
        self._check.blockSignals(True)
        self._check.setChecked(checked)
        self._check.blockSignals(False)
