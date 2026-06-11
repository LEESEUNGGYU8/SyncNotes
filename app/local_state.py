from __future__ import annotations

import json
import time
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
class UserRecord:
    """타임스탬프는 모두 epoch 밀리초 단위다.

    - ``last_joined_at`` 은 현재 세션 시작 시각이며, 0이면 지속 시간 미상.
    - ``last_disconnected_at`` 은 이전 세션이 실제로 끊긴 시각이다.
    """
    last_seen_at: int = 0
    last_joined_at: int = 0
    last_disconnected_at: int = 0


@dataclass
class LocalState:
    nickname: str = ""
    last_host_ip: str = "127.0.0.1"
    last_host_port: int = config.DEFAULT_PORT
    last_mode: str = ""   # "" | "host" | "guest" — 자동 재접속 판단용
    last_heartbeat_ms: int = config.DEFAULT_HEARTBEAT_MS
    notes: dict[str, NoteLocalState] = field(default_factory=dict)
    users: dict[str, UserRecord] = field(default_factory=dict)

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

    def touch_user(self, nickname: str, joined: bool = False, *,
                   disconnected: bool = False) -> UserRecord:
        """``joined`` 이면 ``last_joined_at`` 을, ``disconnected`` 이면
        ``last_disconnected_at`` 을 함께 갱신한다."""
        if not nickname:
            return UserRecord()
        rec = self.users.get(nickname) or UserRecord()
        ts = int(time.time() * 1000)
        rec.last_seen_at = ts
        if joined:
            rec.last_joined_at = ts
        if disconnected:
            rec.last_disconnected_at = ts
        self.users[nickname] = rec
        return rec

    def touch_user_in_session(self, nickname: str, *, is_self: bool) -> UserRecord:
        """welcome 명단을 처리할 때 쓴다.

        접속 시점에 이미 명단에 있던 다른 참가자의 join 시각은 알 수 없으므로,
        ``last_joined_at`` 을 본인에게만 지금 시각으로 찍고
        나머지는 0(미상)으로 둔다. 이후 ``user_joined`` 이벤트가 오면
        정확한 시각으로 갱신된다."""
        if not nickname:
            return UserRecord()
        rec = self.users.get(nickname) or UserRecord()
        ts = int(time.time() * 1000)
        rec.last_seen_at = ts
        rec.last_joined_at = ts if is_self else 0
        self.users[nickname] = rec
        return rec


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
            users: dict[str, UserRecord] = {}
            for nick, payload in raw.get("users", {}).items():
                if not isinstance(payload, dict):
                    continue
                users[nick] = UserRecord(
                    last_seen_at=int(payload.get("last_seen_at", 0)),
                    last_joined_at=int(payload.get("last_joined_at", 0)),
                    last_disconnected_at=int(
                        payload.get("last_disconnected_at", 0)),
                )
            return LocalState(
                nickname=raw.get("nickname", ""),
                last_host_ip=raw.get("last_host_ip", "127.0.0.1"),
                last_host_port=raw.get("last_host_port", config.DEFAULT_PORT),
                last_mode=raw.get("last_mode", ""),
                last_heartbeat_ms=raw.get("last_heartbeat_ms",
                                           config.DEFAULT_HEARTBEAT_MS),
                notes=notes,
                users=users,
            )
        except (json.JSONDecodeError, TypeError, ValueError):
            return LocalState()

    def save(self) -> None:
        data = {
            "nickname": self.state.nickname,
            "last_host_ip": self.state.last_host_ip,
            "last_host_port": self.state.last_host_port,
            "last_mode": self.state.last_mode,
            "last_heartbeat_ms": self.state.last_heartbeat_ms,
            "notes": {nid: asdict(v) for nid, v in self.state.notes.items()},
            "users": {n: asdict(v) for n, v in self.state.users.items()},
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")
