from __future__ import annotations

from PySide6.QtCore import QObject, QTimer

from ..models import new_id
from ..protocol import (
    MSG_ACQUIRE_LOCK,
    MSG_CREATE_FOLDER,
    MSG_CREATE_NOTE,
    MSG_DELETE_FOLDER,
    MSG_DELETE_NOTE,
    MSG_GET_HISTORY,
    MSG_HELLO,
    MSG_RELEASE_LOCK,
    MSG_SET_NOTE_FOLDER,
    MSG_SET_NOTE_PRIVACY,
    MSG_UPDATE_FOLDER,
    MSG_UPDATE_NOTE,
    make,
)
from .client_base import ClientBase
from .host_server import HostServer


class HostLocalClient(ClientBase):
    """게스트와 같은 프로토콜을 쓰되, TCP 없이 HostServer 메서드를 직접
    호출하는 호스트 UI용 in-process 클라이언트."""

    def __init__(self, server: HostServer, nickname: str, parent: QObject | None = None):
        super().__init__(nickname, parent)
        self._server = server

    def start(self) -> None:
        self._server.attach_local_host()
        self._server.set_local_subscriber(self._on_local_event)
        self.connectionChanged.emit(True)
        # HELLO를 다음 tick에 보내야, start() 직후 시그널을 연결하는 UI도
        # 응답으로 오는 welcome 스냅샷을 받을 수 있다.
        QTimer.singleShot(0, self._send_hello)

    def _send_hello(self) -> None:
        self._server.handle_from_local(make(MSG_HELLO, nickname=self._nickname))

    def stop(self) -> None:
        self._server.set_local_subscriber(None)
        self.connectionChanged.emit(False)

    def _on_local_event(self, msg_type: str, data: dict) -> None:
        self._dispatch(msg_type, data)

    def acquire_lock(self, note_id: str) -> None:
        self._server.handle_from_local(make(MSG_ACQUIRE_LOCK, note_id=note_id))

    def release_lock(self, note_id: str) -> None:
        self._server.handle_from_local(make(MSG_RELEASE_LOCK, note_id=note_id))

    def create_note(self, color: str, width: int, height: int,
                    folder_id: str | None = None,
                    private_owner: str | None = None) -> None:
        self._server.handle_from_local(make(
            MSG_CREATE_NOTE, id=new_id(), color=color,
            width=width, height=height,
            folder_id=folder_id, private_owner=private_owner,
        ))

    def set_note_folder(self, note_id: str,
                         folder_id: str | None) -> None:
        self._server.handle_from_local(make(
            MSG_SET_NOTE_FOLDER, id=note_id, folder_id=folder_id))

    def set_note_privacy(self, note_id: str, private: bool) -> None:
        self._server.handle_from_local(make(
            MSG_SET_NOTE_PRIVACY, id=note_id, private=private))

    def create_folder(self, name: str, color: str,
                      private: bool = False) -> None:
        self._server.handle_from_local(make(
            MSG_CREATE_FOLDER, id=new_id(), name=name,
            color=color, private=private))

    def update_folder(self, folder_id: str, *,
                       name: str | None = None,
                       color: str | None = None,
                       private: bool | None = None) -> None:
        payload: dict = {"id": folder_id}
        if name is not None:
            payload["name"] = name
        if color is not None:
            payload["color"] = color
        if private is not None:
            payload["private"] = private
        self._server.handle_from_local(make(MSG_UPDATE_FOLDER, **payload))

    def delete_folder(self, folder_id: str) -> None:
        self._server.handle_from_local(make(
            MSG_DELETE_FOLDER, id=folder_id))

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
