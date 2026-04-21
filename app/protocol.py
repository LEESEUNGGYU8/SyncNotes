from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from typing import Any

LENGTH_HEADER = struct.Struct(">I")  # 4-byte big-endian unsigned int

# Client -> Server
MSG_HELLO = "hello"
MSG_ACQUIRE_LOCK = "acquire_lock"
MSG_RELEASE_LOCK = "release_lock"
MSG_CREATE_NOTE = "create_note"
MSG_UPDATE_NOTE = "update_note"
MSG_DELETE_NOTE = "delete_note"
MSG_PONG = "pong"
MSG_GET_HISTORY = "get_history"

# Server -> Client
MSG_WELCOME = "welcome"
MSG_LOCK_GRANTED = "lock_granted"
MSG_LOCK_DENIED = "lock_denied"
MSG_LOCK_HELD = "lock_held"
MSG_LOCK_RELEASED = "lock_released"
MSG_NOTE_CREATED = "note_created"
MSG_NOTE_UPDATED = "note_updated"
MSG_NOTE_DELETED = "note_deleted"
MSG_HISTORY_APPENDED = "history_appended"
MSG_HISTORY_LIST = "history_list"
MSG_USER_JOINED = "user_joined"
MSG_USER_LEFT = "user_left"
MSG_PING = "ping"
MSG_ERROR = "error"


@dataclass
class Message:
    type: str
    data: dict[str, Any]

    def encode(self) -> bytes:
        body = json.dumps({"type": self.type, "data": self.data}).encode("utf-8")
        return LENGTH_HEADER.pack(len(body)) + body


class FrameParser:
    """Incrementally parse length-prefixed JSON frames from a byte stream."""

    def __init__(self) -> None:
        self._buf = bytearray()

    def feed(self, chunk: bytes) -> list[Message]:
        self._buf.extend(chunk)
        out: list[Message] = []
        while True:
            if len(self._buf) < LENGTH_HEADER.size:
                break
            (length,) = LENGTH_HEADER.unpack_from(self._buf, 0)
            total = LENGTH_HEADER.size + length
            if len(self._buf) < total:
                break
            body = bytes(self._buf[LENGTH_HEADER.size:total])
            del self._buf[:total]
            try:
                payload = json.loads(body.decode("utf-8"))
                out.append(Message(type=payload["type"], data=payload.get("data", {})))
            except (json.JSONDecodeError, KeyError, UnicodeDecodeError):
                # Skip malformed frame; real protocol would close the connection.
                continue
        return out


def make(msg_type: str, **data: Any) -> Message:
    return Message(type=msg_type, data=data)
