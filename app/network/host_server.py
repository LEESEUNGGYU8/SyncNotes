from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtNetwork import QHostAddress, QTcpServer, QTcpSocket

from .. import config
from ..database import SqliteRepository
from ..models import Note, new_id, now_ms
from ..protocol import (
    FrameParser,
    MSG_ACQUIRE_LOCK,
    MSG_CREATE_NOTE,
    MSG_DELETE_NOTE,
    MSG_ERROR,
    MSG_GET_HISTORY,
    MSG_HELLO,
    MSG_HISTORY_APPENDED,
    MSG_HISTORY_LIST,
    MSG_LOCK_DENIED,
    MSG_LOCK_GRANTED,
    MSG_LOCK_HELD,
    MSG_LOCK_RELEASED,
    MSG_NOTE_CREATED,
    MSG_NOTE_DELETED,
    MSG_NOTE_UPDATED,
    MSG_PING,
    MSG_RELEASE_LOCK,
    MSG_UPDATE_NOTE,
    MSG_USER_JOINED,
    MSG_USER_LEFT,
    MSG_WELCOME,
    Message,
    make,
)
from ..sync.history_tracker import HistoryTracker
from ..sync.lock_manager import LockManager


@dataclass
class _Session:
    socket: QTcpSocket | None   # None = local host session
    parser: FrameParser
    nickname: str = ""
    hello_received: bool = False


LocalSubscriber = Callable[[str, dict], None]


class HostServer(QObject):
    """Combined TCP server + authoritative state engine.

    UI never talks to sessions directly. Remote guests use TCP; host UI uses
    set_local_subscriber + handle_from_local to interact through the same
    pipeline.
    """

    serverStarted = Signal(int)               # port
    serverStopped = Signal()
    serverError = Signal(str)

    def __init__(
        self,
        repo: SqliteRepository,
        lock_manager: LockManager,
        history_tracker: HistoryTracker,
        host_nickname: str,
        heartbeat_ms: int = config.DEFAULT_HEARTBEAT_MS,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.repo = repo
        self.locks = lock_manager
        self.history = history_tracker
        self.host_nickname = host_nickname
        self.heartbeat_ms = heartbeat_ms

        self._server = QTcpServer(self)
        self._server.newConnection.connect(self._on_new_connection)
        self._sessions: dict[QTcpSocket, _Session] = {}
        self._local: _Session | None = None
        self._local_subscriber: LocalSubscriber | None = None

        self._heartbeat_timer = QTimer(self)
        self._heartbeat_timer.timeout.connect(self._on_heartbeat)

        self._idle_reap_timer = QTimer(self)
        self._idle_reap_timer.timeout.connect(self._on_idle_reap)

    # ---- lifecycle ----
    def start(self, port: int) -> bool:
        if not self._server.listen(QHostAddress.Any, port):
            self.serverError.emit(self._server.errorString())
            return False
        self._heartbeat_timer.start(self.heartbeat_ms)
        self._idle_reap_timer.start(30_000)
        self.serverStarted.emit(self._server.serverPort())
        return True

    def stop(self) -> None:
        self._heartbeat_timer.stop()
        self._idle_reap_timer.stop()
        for sock in list(self._sessions):
            sock.disconnectFromHost()
            sock.deleteLater()
        self._sessions.clear()
        self._server.close()
        self.serverStopped.emit()

    # ---- local host hooks ----
    def set_local_subscriber(self, cb: LocalSubscriber | None) -> None:
        self._local_subscriber = cb

    def attach_local_host(self) -> None:
        """Register host itself as a session so broadcasts reach host UI too."""
        self._local = _Session(socket=None, parser=FrameParser(),
                               nickname=self.host_nickname, hello_received=True)
        # No user_joined broadcast for host (they're the anchor).

    def handle_from_local(self, msg: Message) -> None:
        assert self._local is not None, "call attach_local_host() first"
        self._handle(self._local, msg)

    # ---- connection management ----
    def _on_new_connection(self) -> None:
        while self._server.hasPendingConnections():
            sock = self._server.nextPendingConnection()
            session = _Session(socket=sock, parser=FrameParser())
            self._sessions[sock] = session
            sock.readyRead.connect(lambda s=sock: self._on_ready_read(s))
            sock.disconnected.connect(lambda s=sock: self._on_disconnected(s))

    def _on_ready_read(self, sock: QTcpSocket) -> None:
        session = self._sessions.get(sock)
        if session is None:
            return
        chunk = bytes(sock.readAll())
        for msg in session.parser.feed(chunk):
            self._handle(session, msg)

    def _on_disconnected(self, sock: QTcpSocket) -> None:
        session = self._sessions.pop(sock, None)
        if session is None:
            return
        if session.nickname:
            released = self.locks.release_all_by(session.nickname)
            for nid in released:
                self.history.cancel_session(nid, session.nickname)
                self._broadcast(make(MSG_LOCK_RELEASED, note_id=nid))
            self._broadcast(make(MSG_USER_LEFT, nickname=session.nickname))
        sock.deleteLater()

    # ---- sending ----
    def _send_to(self, session: _Session, msg: Message) -> None:
        if session.socket is None:
            if self._local_subscriber is not None:
                self._local_subscriber(msg.type, msg.data)
        else:
            session.socket.write(msg.encode())

    def _broadcast(self, msg: Message, exclude: _Session | None = None) -> None:
        for s in self._sessions.values():
            if s is exclude or not s.hello_received:
                continue
            self._send_to(s, msg)
        if self._local is not None and self._local is not exclude:
            self._send_to(self._local, msg)

    def _current_users(self) -> list[str]:
        users = [s.nickname for s in self._sessions.values() if s.hello_received]
        if self._local:
            users.append(self._local.nickname)
        return users

    # ---- dispatch ----
    def _handle(self, session: _Session, msg: Message) -> None:
        t = msg.type
        d = msg.data
        if t == MSG_HELLO:
            self._handle_hello(session, d.get("nickname", "anon"))
        elif not session.hello_received and session is not self._local:
            self._send_to(session, make(MSG_ERROR, message="hello required first"))
        elif t == MSG_ACQUIRE_LOCK:
            self._handle_acquire(session, d.get("note_id", ""))
        elif t == MSG_RELEASE_LOCK:
            self._handle_release(session, d.get("note_id", ""))
        elif t == MSG_CREATE_NOTE:
            self._handle_create(session, d)
        elif t == MSG_UPDATE_NOTE:
            self._handle_update(session, d)
        elif t == MSG_DELETE_NOTE:
            self._handle_delete(session, d.get("id", ""))
        elif t == MSG_GET_HISTORY:
            self._handle_get_history(session, d.get("note_id"))
        # 'pong' is a no-op.

    def _handle_hello(self, session: _Session, nickname: str) -> None:
        session.nickname = nickname or "anon"
        session.hello_received = True
        notes = [n.to_dict() for n in self.repo.list_notes()]
        welcome = make(
            MSG_WELCOME,
            heartbeat_ms=self.heartbeat_ms,
            notes=notes,
            locks=self.locks.snapshot(),
            users=self._current_users(),
        )
        self._send_to(session, welcome)
        self._broadcast(make(MSG_USER_JOINED, nickname=session.nickname),
                        exclude=session)

    def _handle_acquire(self, session: _Session, note_id: str) -> None:
        note = self.repo.get_note(note_id)
        if note is None or note.deleted:
            self._send_to(session, make(MSG_LOCK_DENIED, note_id=note_id,
                                         holder="", reason="not_found"))
            return
        granted, holder = self.locks.acquire(note_id, session.nickname)
        if granted:
            self.history.begin_session(note, session.nickname)
            self._send_to(session, make(MSG_LOCK_GRANTED, note_id=note_id))
            self._broadcast(make(MSG_LOCK_HELD, note_id=note_id,
                                 holder=session.nickname), exclude=session)
        else:
            self._send_to(session, make(MSG_LOCK_DENIED, note_id=note_id,
                                         holder=holder or ""))

    def _handle_release(self, session: _Session, note_id: str) -> None:
        note = self.repo.get_note(note_id)
        if note is not None:
            entry = self.history.end_session(note, session.nickname)
            if entry is not None:
                self._broadcast(make(MSG_HISTORY_APPENDED, entry=entry.to_dict()))
        if self.locks.release(note_id, session.nickname):
            self._broadcast(make(MSG_LOCK_RELEASED, note_id=note_id))

    def _handle_create(self, session: _Session, d: dict) -> None:
        note = Note.new(user=session.nickname, color=d.get("color"))
        if "id" in d and d["id"]:
            note.id = d["id"]
        note.width = int(d.get("width", note.width))
        note.height = int(d.get("height", note.height))
        self.repo.insert_note(note)
        entry = self.history.record_create(note, session.nickname)
        self._broadcast(make(MSG_NOTE_CREATED, note=note.to_dict()))
        self._broadcast(make(MSG_HISTORY_APPENDED, entry=entry.to_dict()))

    def _handle_update(self, session: _Session, d: dict) -> None:
        note_id = d.get("id", "")
        holder = self.locks.holder(note_id)
        if holder and holder != session.nickname:
            self._send_to(session, make(MSG_ERROR,
                message=f"note locked by {holder}"))
            return
        self.locks.touch(note_id, session.nickname)
        updated = self.repo.update_note(
            note_id=note_id,
            content=d.get("content", ""),
            color=d.get("color", config.DEFAULT_COLOR),
            width=int(d.get("width", config.DEFAULT_NOTE_WIDTH)),
            height=int(d.get("height", config.DEFAULT_NOTE_HEIGHT)),
            user=session.nickname,
            expected_version=d.get("expected_version"),
        )
        if updated is None:
            self._send_to(session, make(MSG_ERROR,
                message="update rejected (version mismatch or missing)"))
            return
        self._broadcast(make(MSG_NOTE_UPDATED, note=updated.to_dict()))

    def _handle_delete(self, session: _Session, note_id: str) -> None:
        holder = self.locks.holder(note_id)
        if holder and holder != session.nickname:
            self._send_to(session, make(MSG_ERROR,
                message=f"note locked by {holder}"))
            return
        existing = self.repo.get_note(note_id)
        if existing is None or existing.deleted:
            return
        entry = self.history.record_delete(existing, session.nickname)
        self.repo.soft_delete_note(note_id, session.nickname)
        self.locks.release(note_id, session.nickname)
        self._broadcast(make(MSG_NOTE_DELETED, id=note_id))
        self._broadcast(make(MSG_HISTORY_APPENDED, entry=entry.to_dict()))

    def _handle_get_history(self, session: _Session, note_id: str | None) -> None:
        entries = [e.to_dict() for e in self.repo.list_history(note_id)]
        self._send_to(session, make(MSG_HISTORY_LIST,
                                     note_id=note_id or "",
                                     entries=entries))

    # ---- housekeeping ----
    def _on_heartbeat(self) -> None:
        self._broadcast(make(MSG_PING, ts=now_ms()))

    def _on_idle_reap(self) -> None:
        for nid in self.locks.reap_idle():
            # No session nickname available; history session stays dangling but
            # will be harmless (its begin state will be overwritten next acquire).
            self._broadcast(make(MSG_LOCK_RELEASED, note_id=nid))
