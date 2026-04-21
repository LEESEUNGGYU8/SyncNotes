from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from . import config


@dataclass
class NoteLocalState:
    x: int = 120
    y: int = 120
    hidden: bool = False


@dataclass
class LocalState:
    nickname: str = ""
    last_host_ip: str = "127.0.0.1"
    last_host_port: int = config.DEFAULT_PORT
    notes: dict[str, NoteLocalState] = field(default_factory=dict)

    def get_note_state(self, note_id: str) -> NoteLocalState:
        if note_id not in self.notes:
            self.notes[note_id] = NoteLocalState()
        return self.notes[note_id]

    def set_note_state(
        self, note_id: str, x: int | None = None, y: int | None = None,
        hidden: bool | None = None,
    ) -> NoteLocalState:
        state = self.get_note_state(note_id)
        if x is not None:
            state.x = x
        if y is not None:
            state.y = y
        if hidden is not None:
            state.hidden = hidden
        return state

    def remove_note(self, note_id: str) -> None:
        self.notes.pop(note_id, None)


class LocalStateStore:
    def __init__(self, path: Path | None = None):
        self.path = path or config.default_local_state_path()
        self.state = self._load()

    def _load(self) -> LocalState:
        if not self.path.exists():
            return LocalState()
        try:
            raw: dict[str, Any] = json.loads(self.path.read_text(encoding="utf-8"))
            notes = {
                nid: NoteLocalState(**v) for nid, v in raw.get("notes", {}).items()
            }
            return LocalState(
                nickname=raw.get("nickname", ""),
                last_host_ip=raw.get("last_host_ip", "127.0.0.1"),
                last_host_port=raw.get("last_host_port", config.DEFAULT_PORT),
                notes=notes,
            )
        except (json.JSONDecodeError, TypeError, ValueError):
            return LocalState()

    def save(self) -> None:
        data = {
            "nickname": self.state.nickname,
            "last_host_ip": self.state.last_host_ip,
            "last_host_port": self.state.last_host_port,
            "notes": {nid: asdict(v) for nid, v in self.state.notes.items()},
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")
