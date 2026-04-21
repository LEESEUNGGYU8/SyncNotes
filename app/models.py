from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any

from . import config


def now_ms() -> int:
    return int(time.time() * 1000)


def new_id() -> str:
    return uuid.uuid4().hex


@dataclass
class Note:
    id: str
    content: str = ""
    color: str = config.DEFAULT_COLOR
    width: int = config.DEFAULT_NOTE_WIDTH
    height: int = config.DEFAULT_NOTE_HEIGHT
    created_by: str = ""
    created_at: int = 0
    updated_by: str = ""
    updated_at: int = 0
    version: int = 1
    deleted: int = 0

    @classmethod
    def new(cls, user: str, color: str | None = None) -> "Note":
        t = now_ms()
        return cls(
            id=new_id(),
            color=color or config.DEFAULT_COLOR,
            created_by=user,
            created_at=t,
            updated_by=user,
            updated_at=t,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Note":
        return cls(**data)


@dataclass
class HistoryEntry:
    note_id: str
    user: str
    action: str  # 'create' | 'update' | 'delete'
    content_before: str | None
    content_after: str | None
    color_before: str | None
    color_after: str | None
    session_start: int
    session_end: int
    id: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HistoryEntry":
        return cls(**data)


@dataclass
class UserSession:
    nickname: str
    connected_at: int = field(default_factory=now_ms)
