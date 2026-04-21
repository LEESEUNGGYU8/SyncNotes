from __future__ import annotations

from PySide6.QtCore import QObject, QTimer

from .. import config
from ..models import new_id
from ..protocol import (
    MSG_ACQUIRE_LOCK,
    MSG_CREATE_NOTE,
    MSG_DELETE_NOTE,
    MSG_GET_HISTORY,
    MSG_HELLO,
    MSG_RELEASE_LOCK,
    MSG_UPDATE_NOTE,
    make,
)
from .client_base import ClientBase
from .host_server import HostServer


class HostLocalClient(ClientBase):
    """In-process client used by the host's own UI. Speaks the same protocol
    messages, but bypasses TCP by directly invoking HostServer methods."""

    def __init__(self, server: HostServer, nickname: str, parent: QObject | None = None):
        super().__init__(nickname, parent)
        self._server = server

    def start(self) -> None:
        self._server.attach_local_host()
        self._server.set_local_subscriber(self._on_local_event)
        self.connectionChanged.emit(True)
        self._server.handle_from_local(make(MSG_HELLO, nickname=self._nickname))

    def stop(self) -> None:
        self._server.set_local_subscriber(None)
        self.connectionChanged.emit(False)

    def _on_local_event(self, msg_type: str, data: dict) -> None:
        self._dispatch(msg_type, data)

    # ---- actions ----
    def acquire_lock(self, note_id: str) -> None:
        self._server.handle_from_local(make(MSG_ACQUIRE_LOCK, note_id=note_id))

    def release_lock(self, note_id: str) -> None:
        self._server.handle_from_local(make(MSG_RELEASE_LOCK, note_id=note_id))

    def create_note(self, color: str, width: int, height: int) -> None:
        self._server.handle_from_local(make(
            MSG_CREATE_NOTE, id=new_id(), color=color,
            width=width, height=height,
        ))

    def update_note(
        self, note_id: str, content: str, color: str, width: int, height: int,
        expected_version: int,
    ) -> None:
        self._server.handle_from_local(make(
            MSG_UPDATE_NOTE, id=note_id, content=content, color=color,
            width=width, height=height, expected_version=expected_version,
        ))

    def delete_note(self, note_id: str) -> None:
        self._server.handle_from_local(make(MSG_DELETE_NOTE, id=note_id))

    def get_history(self, note_id: str | None = None) -> None:
        self._server.handle_from_local(make(MSG_GET_HISTORY, note_id=note_id))
