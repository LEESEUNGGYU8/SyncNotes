from __future__ import annotations

from dataclasses import dataclass

from ..models import now_ms


@dataclass
class LockEntry:
    holder: str
    acquired_at: int
    last_activity: int


class LockManager:
    def __init__(self, idle_timeout_ms: int):
        self._locks: dict[str, LockEntry] = {}
        self.idle_timeout_ms = idle_timeout_ms

    def snapshot(self) -> dict[str, str]:
        return {nid: entry.holder for nid, entry in self._locks.items()}

    def holder(self, note_id: str) -> str | None:
        entry = self._locks.get(note_id)
        return entry.holder if entry else None

    def acquire(self, note_id: str, user: str) -> tuple[bool, str | None]:
        """``(획득 성공 여부, 현재 보유자)`` 를 반환한다."""
        existing = self._locks.get(note_id)
        if existing and existing.holder != user:
            return False, existing.holder
        t = now_ms()
        self._locks[note_id] = LockEntry(holder=user, acquired_at=t, last_activity=t)
        return True, user

    def touch(self, note_id: str, user: str) -> None:
        entry = self._locks.get(note_id)
        if entry and entry.holder == user:
            entry.last_activity = now_ms()

    def release(self, note_id: str, user: str) -> bool:
        entry = self._locks.get(note_id)
        if entry and entry.holder == user:
            del self._locks[note_id]
            return True
        return False

    def release_all_by(self, user: str) -> list[str]:
        released = [nid for nid, e in self._locks.items() if e.holder == user]
        for nid in released:
            del self._locks[nid]
        return released

    def reap_idle(self) -> list[str]:
        t = now_ms()
        stale = [
            nid for nid, e in self._locks.items()
            if t - e.last_activity > self.idle_timeout_ms
        ]
        for nid in stale:
            del self._locks[nid]
        return stale
