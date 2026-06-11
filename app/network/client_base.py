from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Signal


class ClientBase(QObject):
    """게스트(TCP)와 호스트(in-process)가 같은 시그널을 제공해, UI가
    역할에 따라 분기하지 않아도 되게 하는 통합 인터페이스."""

    welcomed = Signal(dict)                  # {heartbeat_ms, notes, locks, users, folders, host}
    noteCreated = Signal(dict)
    noteUpdated = Signal(dict)
    noteDeleted = Signal(str)
    folderCreated = Signal(dict)
    folderUpdated = Signal(dict)
    folderDeleted = Signal(str)
    lockGranted = Signal(str)
    lockDenied = Signal(str, str)            # note_id, holder
    lockHeld = Signal(str, str)              # note_id, holder
    lockReleased = Signal(str)
    userJoined = Signal(str)
    userLeft = Signal(str)
    historyAppended = Signal(dict)
    historyList = Signal(str, list)          # note_id 또는 '', [entries]
    connectionChanged = Signal(bool)
    errorOccurred = Signal(str)

    def __init__(self, nickname: str, parent: QObject | None = None):
        super().__init__(parent)
        self._nickname = nickname

    def nickname(self) -> str:
        return self._nickname

    def start(self) -> None: ...
    def stop(self) -> None: ...

    def acquire_lock(self, note_id: str) -> None: ...
    def release_lock(self, note_id: str) -> None: ...
    def create_note(self, color: str, width: int, height: int,
                    folder_id: str | None = None,
                    private_owner: str | None = None) -> None: ...
    def update_note(
        self, note_id: str, content: str, color: str, width: int, height: int,
        expected_version: int,
    ) -> None: ...
    def delete_note(self, note_id: str) -> None: ...
    def set_note_folder(self, note_id: str, folder_id: str | None) -> None: ...
    def set_note_privacy(self, note_id: str, private: bool) -> None: ...
    def create_folder(self, name: str, color: str,
                      private: bool = False) -> None: ...
    def update_folder(self, folder_id: str, *,
                       name: str | None = None,
                       color: str | None = None,
                       private: bool | None = None) -> None: ...
    def delete_folder(self, folder_id: str) -> None: ...
    def get_history(self, note_id: str | None = None) -> None: ...

    def _dispatch(self, msg_type: str, data: dict[str, Any]) -> None:
        if msg_type == "welcome":
            self.welcomed.emit(data)
        elif msg_type == "note_created":
            self.noteCreated.emit(data.get("note", {}))
        elif msg_type == "note_updated":
            self.noteUpdated.emit(data.get("note", {}))
        elif msg_type == "note_deleted":
            self.noteDeleted.emit(data.get("id", ""))
        elif msg_type == "folder_created":
            self.folderCreated.emit(data.get("folder", {}))
        elif msg_type == "folder_updated":
            self.folderUpdated.emit(data.get("folder", {}))
        elif msg_type == "folder_deleted":
            self.folderDeleted.emit(data.get("id", ""))
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
