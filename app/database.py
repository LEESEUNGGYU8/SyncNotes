from __future__ import annotations

import sqlite3
from pathlib import Path

from .models import HistoryEntry, Note, now_ms

SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
  id            TEXT PRIMARY KEY,
  content       TEXT NOT NULL DEFAULT '',
  color         TEXT NOT NULL,
  width         INTEGER NOT NULL DEFAULT 240,
  height        INTEGER NOT NULL DEFAULT 200,
  created_by    TEXT NOT NULL,
  created_at    INTEGER NOT NULL,
  updated_by    TEXT NOT NULL,
  updated_at    INTEGER NOT NULL,
  version       INTEGER NOT NULL DEFAULT 1,
  deleted       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS note_history (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  note_id        TEXT NOT NULL,
  user           TEXT NOT NULL,
  action         TEXT NOT NULL,
  content_before TEXT,
  content_after  TEXT,
  color_before   TEXT,
  color_after    TEXT,
  session_start  INTEGER NOT NULL,
  session_end    INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_hist_note ON note_history(note_id, session_end DESC);
"""


class SqliteRepository:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # --- notes ---

    def list_notes(self, include_deleted: bool = False) -> list[Note]:
        q = "SELECT * FROM notes"
        if not include_deleted:
            q += " WHERE deleted = 0"
        q += " ORDER BY created_at ASC"
        rows = self._conn.execute(q).fetchall()
        return [Note(**dict(r)) for r in rows]

    def get_note(self, note_id: str) -> Note | None:
        row = self._conn.execute(
            "SELECT * FROM notes WHERE id = ?", (note_id,)
        ).fetchone()
        return Note(**dict(row)) if row else None

    def insert_note(self, note: Note) -> None:
        self._conn.execute(
            """INSERT INTO notes
               (id, content, color, width, height, created_by, created_at,
                updated_by, updated_at, version, deleted)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                note.id, note.content, note.color, note.width, note.height,
                note.created_by, note.created_at, note.updated_by, note.updated_at,
                note.version, note.deleted,
            ),
        )
        self._conn.commit()

    def update_note(
        self, note_id: str, content: str, color: str, width: int, height: int,
        user: str, expected_version: int | None = None,
    ) -> Note | None:
        existing = self.get_note(note_id)
        if existing is None or existing.deleted:
            return None
        if expected_version is not None and existing.version != expected_version:
            return None
        new_version = existing.version + 1
        t = now_ms()
        self._conn.execute(
            """UPDATE notes SET content = ?, color = ?, width = ?, height = ?,
                                updated_by = ?, updated_at = ?, version = ?
               WHERE id = ?""",
            (content, color, width, height, user, t, new_version, note_id),
        )
        self._conn.commit()
        return self.get_note(note_id)

    def soft_delete_note(self, note_id: str, user: str) -> Note | None:
        existing = self.get_note(note_id)
        if existing is None or existing.deleted:
            return None
        t = now_ms()
        self._conn.execute(
            """UPDATE notes SET deleted = 1, updated_by = ?, updated_at = ?,
                                version = version + 1
               WHERE id = ?""",
            (user, t, note_id),
        )
        self._conn.commit()
        return self.get_note(note_id)

    # --- history ---

    def insert_history(self, entry: HistoryEntry) -> HistoryEntry:
        cur = self._conn.execute(
            """INSERT INTO note_history
               (note_id, user, action, content_before, content_after,
                color_before, color_after, session_start, session_end)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entry.note_id, entry.user, entry.action,
                entry.content_before, entry.content_after,
                entry.color_before, entry.color_after,
                entry.session_start, entry.session_end,
            ),
        )
        self._conn.commit()
        entry.id = cur.lastrowid or 0
        return entry

    def list_history(self, note_id: str | None = None) -> list[HistoryEntry]:
        if note_id is None:
            rows = self._conn.execute(
                "SELECT * FROM note_history ORDER BY session_end DESC"
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM note_history WHERE note_id = ? ORDER BY session_end DESC",
                (note_id,),
            ).fetchall()
        return [HistoryEntry(**dict(r)) for r in rows]
