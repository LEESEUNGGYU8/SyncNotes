from __future__ import annotations

from PySide6.QtCore import QObject, QTimer
from PySide6.QtNetwork import QAbstractSocket, QTcpSocket

from ..models import new_id
from ..protocol import (
    FrameParser,
    MSG_ACQUIRE_LOCK,
    MSG_CREATE_FOLDER,
    MSG_CREATE_NOTE,
    MSG_DELETE_FOLDER,
    MSG_DELETE_NOTE,
    MSG_GET_HISTORY,
    MSG_HELLO,
    MSG_PING,
    MSG_PONG,
    MSG_RELEASE_LOCK,
    MSG_SET_NOTE_FOLDER,
    MSG_SET_NOTE_PRIVACY,
    MSG_UPDATE_FOLDER,
    MSG_UPDATE_NOTE,
    Message,
    make,
)
from .client_base import ClientBase


RECONNECT_BACKOFF_MS = (1000, 2000, 4000, 8000)


class GuestClient(ClientBase):
    def __init__(self, host: str, port: int, nickname: str,
                 parent: QObject | None = None):
        super().__init__(nickname, parent)
        self._host = host
        self._port = port
        self._sock = QTcpSocket(self)
        self._parser = FrameParser()
        self._sock.readyRead.connect(self._on_ready_read)
        self._sock.connected.connect(self._on_connected)
        self._sock.disconnected.connect(self._on_disconnected)
        self._sock.errorOccurred.connect(self._on_socket_error)

        self._reconnect_timer = QTimer(self)
        self._reconnect_timer.setSingleShot(True)
        self._reconnect_timer.timeout.connect(self._do_connect)
        self._reconnect_attempt = 0
        self._stopped = False

    def start(self) -> None:
        self._stopped = False
        self._do_connect()

    def stop(self) -> None:
        self._stopped = True
        self._reconnect_timer.stop()
        if self._sock.state() != QAbstractSocket.UnconnectedState:
            self._sock.disconnectFromHost()

    def _do_connect(self) -> None:
        self._parser = FrameParser()
        self._sock.abort()
        self._sock.connectToHost(self._host, self._port)

    def _schedule_reconnect(self) -> None:
        if self._stopped:
            return
        delay = RECONNECT_BACKOFF_MS[min(self._reconnect_attempt,
                                          len(RECONNECT_BACKOFF_MS) - 1)]
        self._reconnect_attempt += 1
        self._reconnect_timer.start(delay)

    def _on_connected(self) -> None:
        self._reconnect_attempt = 0
        self.connectionChanged.emit(True)
        self._send(make(MSG_HELLO, nickname=self._nickname))

    def _on_disconnected(self) -> None:
        self.connectionChanged.emit(False)
        self._schedule_reconnect()

    def _on_socket_error(self, _err) -> None:
        # 연결돼 있었다면 곧 disconnected 가 재연결을 예약하므로, 미연결
        # 상태(connectToHost 실패)일 때만 여기서 직접 예약한다.
        if self._sock.state() == QAbstractSocket.UnconnectedState:
            self._schedule_reconnect()

    def _on_ready_read(self) -> None:
        chunk = bytes(self._sock.readAll())
        for msg in self._parser.feed(chunk):
            if msg.type == MSG_PING:
                self._send(make(MSG_PONG))
                continue
            self._dispatch(msg.type, msg.data)

    def _send(self, msg: Message) -> None:
        if self._sock.state() == QAbstractSocket.ConnectedState:
            self._sock.write(msg.encode())

    def acquire_lock(self, note_id: str) -> None:
        self._send(make(MSG_ACQUIRE_LOCK, note_id=note_id))

    def release_lock(self, note_id: str) -> None:
        self._send(make(MSG_RELEASE_LOCK, note_id=note_id))

    def create_note(self, color: str, width: int, height: int,
                    folder_id: str | None = None,
                    private_owner: str | None = None) -> None:
        self._send(make(MSG_CREATE_NOTE, id=new_id(), color=color,
                        width=width, height=height,
                        folder_id=folder_id,
                        private_owner=private_owner))

    def set_note_folder(self, note_id: str,
                         folder_id: str | None) -> None:
        self._send(make(MSG_SET_NOTE_FOLDER, id=note_id,
                        folder_id=folder_id))

    def set_note_privacy(self, note_id: str, private: bool) -> None:
        self._send(make(MSG_SET_NOTE_PRIVACY, id=note_id,
                        private=private))

    def create_folder(self, name: str, color: str,
                      private: bool = False) -> None:
        self._send(make(MSG_CREATE_FOLDER, id=new_id(), name=name,
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
        self._send(make(MSG_UPDATE_FOLDER, **payload))

    def delete_folder(self, folder_id: str) -> None:
        self._send(make(MSG_DELETE_FOLDER, id=folder_id))

    def update_note(
        self, note_id: str, content: str, color: str, width: int, height: int,
        expected_version: int,
    ) -> None:
        self._send(make(MSG_UPDATE_NOTE, id=note_id, content=content,
                        color=color, width=width, height=height,
                        expected_version=expected_version))

    def delete_note(self, note_id: str) -> None:
        self._send(make(MSG_DELETE_NOTE, id=note_id))

    def get_history(self, note_id: str | None = None) -> None:
        self._send(make(MSG_GET_HISTORY, note_id=note_id))
