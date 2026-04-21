from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Signal


class ClientBase(QObject):
    """Unified interface subscribed by UI. Implemented by both guest (TCP) and
    host-local clients so UI code does not branch on role."""

    welcomed = Signal(dict)                  # {heartbeat_ms, notes, locks, users}
    noteCreated = Signal(dict)               # note dict
    noteUpdated = Signal(dict)
    noteDeleted = Signal(str)                # note_id
    lockGranted = Signal(str)                # note_id
    lockDenied = Signal(str, str)            # note_id, holder
    lockHeld = Signal(str, str)              # note_id, holder
    lockReleased = Signal(str)               # note_id
    userJoined = Signal(str)
    userLeft = Signal(str)
    historyAppended = Signal(dict)           # history entry
    historyList = Signal(str, list)          # note_id_or_'', [entries]
    connectionChanged = Signal(bool)
    errorOccurred = Signal(str)

    def __init__(self, nickname: str, parent: QObject | None = None):
        super().__init__(parent)
        self._nickname = nickname

    def nickname(self) -> str:
        return self._nickname

    # --- lifecycle ---
    def start(self) -> None: ...
    def stop(self) -> None: ...

    # --- actions ---
    def acquire_lock(self, note_id: str) -> None: ...
    def release_lock(self, note_id: str) -> None: ...
    def create_note(self, color: str, width: int, height: int) -> None: ...
    def update_note(
        self, note_id: str, content: str, color: str, width: int, height: int,
        expected_version: int,
    ) -> None: ...
    def delete_note(self, note_id: str) -> None: ...
    def get_history(self, note_id: str | None = None) -> None: ...

    # --- helpers for subclasses dispatching incoming messages ---
    def _dispatch(self, msg_type: str, data: dict[str, Any]) -> None:
        if msg_type == "welcome":
            self.welcomed.emit(data)
        elif msg_type == "note_created":
            self.noteCreated.emit(data.get("note", {}))
        elif msg_type == "note_updated":
            self.noteUpdated.emit(data.get("note", {}))
        elif msg_type == "note_deleted":
            self.noteDeleted.emit(data.get("id", ""))
        elif msg_type == "lock_granted":
            self.lockGranted.emit(data.get("note_id", ""))
        elif msg_type == "lock_denied":
            self.lockDenied.emit(data.get("note_id", ""), data.get("holder", ""))
        elif msg_type == "lock_held":
            self.lockHeld.emit(data.get("note_id", ""), data.get("holder", ""))
        elif msg_type == "lock_released":
            self.lockReleased.emit(data.get("note_id", ""))
        elif msg_type == "user_joined":
            self.userJoined.emit(data.get("nickname", ""))
        elif msg_type == "user_left":
            self.userLeft.emit(data.get("nickname", ""))
        elif msg_type == "history_appended":
            self.historyAppended.emit(data.get("entry", {}))
        elif msg_type == "history_list":
            self.historyList.emit(data.get("note_id", "") or "", data.get("entries", []))
        elif msg_type == "error":
            self.errorOccurred.emit(data.get("message", ""))
