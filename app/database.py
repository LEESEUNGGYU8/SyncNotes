from __future__ import annotations

import sqlite3
from pathlib import Path

from .models import Folder, HistoryEntry, Note, now_ms

_SCHEMA_TABLES = """
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
  deleted       INTEGER NOT NULL DEFAULT 0,
  folder_id     TEXT,
  private_owner TEXT
);

CREATE TABLE IF NOT EXISTS folders (
  id            TEXT PRIMARY KEY,
  name          TEXT NOT NULL,
  color         TEXT NOT NULL DEFAULT '#FFE066',
  created_by    TEXT NOT NULL,
  created_at    INTEGER NOT NULL,
  updated_at    INTEGER NOT NULL,
  private_owner TEXT,
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
"""

# 인덱스를 테이블 생성과 분리해 둔다.
# 구버전 notes 테이블에는 folder_id 컬럼이 없어,
# _migrate 전에 그 컬럼을 참조하는 인덱스를 만들면 실패한다.
# 그래서 '테이블 → _migrate → 인덱스' 순서를 지켜야 한다.
_SCHEMA_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_folders_owner ON folders(private_owner, deleted);
CREATE INDEX IF NOT EXISTS idx_notes_folder ON notes(folder_id, deleted);
CREATE INDEX IF NOT EXISTS idx_hist_note ON note_history(note_id, session_end DESC);
"""


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


def _migrate(conn: sqlite3.Connection) -> None:
    """첫 릴리스 이후 추가된 컬럼들을 구버전 DB에 채워 넣는다."""
    cols = _table_columns(conn, "notes")
    if "folder_id" not in cols:
        conn.execute("ALTER TABLE notes ADD COLUMN folder_id TEXT")
    if "private_owner" not in cols:
        conn.execute("ALTER TABLE notes ADD COLUMN private_owner TEXT")
    conn.commit()


class _Sentinel:
    """'인자를 안 넘긴 경우'와 '명시적으로 None을 넘긴 경우'를 구분한다."""


_UNCHANGED = _Sentinel()


class SqliteRepository:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA_TABLES)
        self._conn.commit()
        _migrate(self._conn)
        self._conn.executescript(_SCHEMA_INDEXES)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

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
                updated_by, updated_at, version, deleted, folder_id,
                private_owner)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                note.id, note.content, note.color, note.width, note.height,
                note.created_by, note.created_at, note.updated_by, note.updated_at,
                note.version, note.deleted, note.folder_id, note.private_owner,
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

    def set_note_folder(self, note_id: str, folder_id: str | None,
                        user: str) -> Note | None:
        existing = self.get_note(note_id)
        if existing is None or existing.deleted:
            return None
        t = now_ms()
        self._conn.execute(
            """UPDATE notes SET folder_id = ?, updated_by = ?, updated_at = ?,
                                version = version + 1
               WHERE id = ?""",
            (folder_id, user, t, note_id),
        )
        self._conn.commit()
        return self.get_note(note_id)

    def set_note_private_owner(self, note_id: str,
                                private_owner: str | None,
                                user: str) -> Note | None:
        existing = self.get_note(note_id)
        if existing is None or existing.deleted:
            return None
        t = now_ms()
        self._conn.execute(
            """UPDATE notes SET private_owner = ?, updated_by = ?,
                                updated_at = ?, version = version + 1
               WHERE id = ?""",
            (private_owner, user, t, note_id),
        )
        self._conn.commit()
        return self.get_note(note_id)

    def list_folders(self, include_deleted: bool = False) -> list[Folder]:
        q = "SELECT * FROM folders"
        if not include_deleted:
            q += " WHERE deleted = 0"
        q += " ORDER BY created_at ASC"
        rows = self._conn.execute(q).fetchall()
        return [Folder(**dict(r)) for r in rows]

    def get_folder(self, folder_id: str) -> Folder | None:
        row = self._conn.execute(
            "SELECT * FROM folders WHERE id = ?", (folder_id,)
        ).fetchone()
        return Folder(**dict(row)) if row else None

    def insert_folder(self, folder: Folder) -> None:
        self._conn.execute(
            """INSERT INTO folders
               (id, name, color, created_by, created_at, updated_at,
                private_owner, deleted)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                folder.id, folder.name, folder.color, folder.created_by,
                folder.created_at, folder.updated_at, folder.private_owner,
                folder.deleted,
            ),
        )
        self._conn.commit()

    def update_folder(self, folder_id: str, *, name: str | None = None,
                       color: str | None = None,
                       private_owner=_UNCHANGED) -> Folder | None:
        existing = self.get_folder(folder_id)
        if existing is None or existing.deleted:
            return None
        new_name = existing.name if name is None else name
        new_color = existing.color if color is None else color
        if private_owner is _UNCHANGED:
            new_owner = existing.private_owner
        else:
            new_owner = private_owner
        t = now_ms()
        self._conn.execute(
            """UPDATE folders SET name = ?, color = ?, private_owner = ?,
                                  updated_at = ?
               WHERE id = ?""",
            (new_name, new_color, new_owner, t, folder_id),
        )
        self._conn.commit()
        return self.get_folder(folder_id)

    def soft_delete_folder(self, folder_id: str) -> Folder | None:
        existing = self.get_folder(folder_id)
        if existing is None or existing.deleted:
            return None
        t = now_ms()
        self._conn.execute(
            "UPDATE folders SET deleted = 1, updated_at = ? WHERE id = ?",
            (t, folder_id),
        )
        # 폴더에 들어 있던 메모는 폴더에서 떼어내 '미분류'로 보낸다.
        self._conn.execute(
            "UPDATE notes SET folder_id = NULL, updated_at = ?"
            " WHERE folder_id = ?",
            (t, folder_id),
        )
        self._conn.commit()
        return self.get_folder(folder_id)

    def list_notes_in_folder(self, folder_id: str) -> list[Note]:
        rows = self._conn.execute(
            "SELECT * FROM notes WHERE folder_id = ? AND deleted = 0"
            " ORDER BY created_at ASC",
            (folder_id,),
        ).fetchall()
        return [Note(**dict(r)) for r in rows]

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
                "SELECT * FROM note_history WHERE note_id = ?"
                " ORDER BY session_end DESC",
                (note_id,),
            ).fetchall()
        return [HistoryEntry(**dict(r)) for r in rows]
