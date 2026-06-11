from __future__ import annotations

from dataclasses import dataclass

from ..database import SqliteRepository
from ..models import HistoryEntry, Note, now_ms


@dataclass
class _PendingSession:
    user: str
    content_before: str
    color_before: str
    session_start: int


class HistoryTracker:
    def __init__(self, repo: SqliteRepository):
        self.repo = repo
        self._pending: dict[str, _PendingSession] = {}

    def begin_session(self, note: Note, user: str) -> None:
        self._pending[note.id] = _PendingSession(
            user=user,
            content_before=note.content,
            color_before=note.color,
            session_start=now_ms(),
        )

    def cancel_session(self, note_id: str, user: str) -> None:
        p = self._pending.get(note_id)
        if p and p.user == user:
            del self._pending[note_id]

    def end_session(self, note: Note, user: str) -> HistoryEntry | None:
        p = self._pending.pop(note.id, None)
        if p is None or p.user != user:
            return None
        if p.content_before == note.content and p.color_before == note.color:
            return None
        entry = HistoryEntry(
            note_id=note.id,
            user=user,
            action="update",
            content_before=p.content_before,
            content_after=note.content,
            color_before=p.color_before,
            color_after=note.color,
            session_start=p.session_start,
            session_end=now_ms(),
        )
        return self.repo.insert_history(entry)

    def record_create(self, note: Note, user: str) -> HistoryEntry:
        t = now_ms()
        entry = HistoryEntry(
            note_id=note.id,
            user=user,
            action="create",
            content_before=None,
            content_after=note.content,
            color_before=None,
            color_after=note.color,
            session_start=t,
            session_end=t,
        )
        return self.repo.insert_history(entry)

    def record_delete(self, note: Note, user: str) -> HistoryEntry:
        t = now_ms()
        entry = HistoryEntry(
            note_id=note.id,
            user=user,
            action="delete",
            content_before=note.content,
            content_after=None,
            color_before=note.color,
            color_after=None,
            session_start=t,
            session_end=t,
        )
        return self.repo.insert_history(entry)
