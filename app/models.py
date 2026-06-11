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
    # None이면 '미분류'.
    folder_id: str | None = None
    # None이면 공개 메모, 닉네임이 있으면 그 참가자에게만 보이는 비공개 메모.
    private_owner: str | None = None

    @classmethod
    def new(cls, user: str, color: str | None = None,
            folder_id: str | None = None,
            private_owner: str | None = None) -> "Note":
        t = now_ms()
        return cls(
            id=new_id(),
            color=color or config.DEFAULT_COLOR,
            created_by=user,
            created_at=t,
            updated_by=user,
            updated_at=t,
            folder_id=folder_id,
            private_owner=private_owner,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Note":
        # 모르는 키를 무시해 구버전 서버가 보낸 dict와도 호환된다.
        known = {k: v for k, v in data.items()
                 if k in cls.__dataclass_fields__}
        return cls(**known)


@dataclass
class Folder:
    """폴더는 중첩되지 않는 평면 구조다. ``private_owner`` 가 지정되면
    폴더와 그 안의 모든 메모가 해당 참가자에게만 보인다."""
    id: str
    name: str
    color: str = config.DEFAULT_COLOR
    created_by: str = ""
    created_at: int = 0
    updated_at: int = 0
    private_owner: str | None = None
    deleted: int = 0

    @classmethod
    def new(cls, user: str, name: str,
            color: str | None = None,
            private_owner: str | None = None) -> "Folder":
        t = now_ms()
        return cls(
            id=new_id(),
            name=name or "새 폴더",
            color=color or config.DEFAULT_COLOR,
            created_by=user,
            created_at=t,
            updated_at=t,
            private_owner=private_owner,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Folder":
        known = {k: v for k, v in data.items()
                 if k in cls.__dataclass_fields__}
        return cls(**known)


@dataclass
class HistoryEntry:
    note_id: str
    user: str
    action: str  # 'create' / 'update' / 'delete'
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
