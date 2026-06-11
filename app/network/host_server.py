from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtNetwork import QHostAddress, QTcpServer, QTcpSocket

from .. import config
from ..database import SqliteRepository
from ..models import Folder, Note, now_ms
from ..protocol import (
    FrameParser,
    MSG_ACQUIRE_LOCK,
    MSG_CREATE_FOLDER,
    MSG_CREATE_NOTE,
    MSG_DELETE_FOLDER,
    MSG_DELETE_NOTE,
    MSG_ERROR,
    MSG_FOLDER_CREATED,
    MSG_FOLDER_DELETED,
    MSG_FOLDER_UPDATED,
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
    MSG_SET_NOTE_FOLDER,
    MSG_SET_NOTE_PRIVACY,
    MSG_UPDATE_FOLDER,
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
    socket: QTcpSocket | None   # None 은 로컬 호스트 세션을 뜻한다.
    parser: FrameParser
    nickname: str = ""
    hello_received: bool = False


LocalSubscriber = Callable[[str, dict], None]


class HostServer(QObject):
    """원격 게스트(TCP)와 호스트 UI(로컬 세션)를 같은 처리 파이프라인으로 합류시킨다."""

    serverStarted = Signal(int)
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

    def set_local_subscriber(self, cb: LocalSubscriber | None) -> None:
        self._local_subscriber = cb

    def attach_local_host(self) -> None:
        self._local = _Session(socket=None, parser=FrameParser(),
                               nickname=self.host_nickname, hello_received=True)
        # 호스트는 항상 존재하는 기준 사용자이므로 user_joined 는 보내지 않는다.

    def handle_from_local(self, msg: Message) -> None:
        assert self._local is not None, "call attach_local_host() first"
        self._handle(self._local, msg)

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

    def _send_to_nickname(self, nickname: str | None,
                            msg: Message) -> None:
        if not nickname:
            return
        for s in self._sessions.values():
            if s.hello_received and s.nickname == nickname:
                self._send_to(s, msg)
        if (self._local is not None
                and self._local.nickname == nickname):
            self._send_to(self._local, msg)

    def _broadcast_to_all_except_nickname(
            self, msg: Message, *, except_nickname: str | None) -> None:
        for s in self._sessions.values():
            if not s.hello_received:
                continue
            if except_nickname and s.nickname == except_nickname:
                continue
            self._send_to(s, msg)
        if self._local is not None:
            if (except_nickname
                    and self._local.nickname == except_nickname):
                return
            self._send_to(self._local, msg)

    def _propagate_audience_change(
            self, note_id: str, note_dict: dict, *,
            prev_owner: str | None, new_owner: str | None) -> None:
        """가시 사용자 집합이 바뀔 때 이벤트를 분배한다.

        접근권을 유지한 사용자에게는 ``note_updated`` 만 보내 그 화면의 메모
        위젯을 깜빡임 없이 살려 둔다. 접근권을 잃은 사용자에게는 ``note_deleted``,
        새로 얻은 사용자에게는 ``note_created`` 를 보낸다."""
        if prev_owner == new_owner:
            self._broadcast_for_owner(
                make(MSG_NOTE_UPDATED, note=note_dict),
                private_owner=new_owner)
            return
        if prev_owner is None and new_owner is not None:
            self._send_to_nickname(
                new_owner,
                make(MSG_NOTE_UPDATED, note=note_dict))
            self._broadcast_to_all_except_nickname(
                make(MSG_NOTE_DELETED, id=note_id),
                except_nickname=new_owner)
            return
        if prev_owner is not None and new_owner is None:
            self._send_to_nickname(
                prev_owner,
                make(MSG_NOTE_UPDATED, note=note_dict))
            self._broadcast_to_all_except_nickname(
                make(MSG_NOTE_CREATED, note=note_dict),
                except_nickname=prev_owner)
            return
        # 비공개 소유자가 다른 사람으로 교체된 경우로, 양쪽에 공통 사용자가 없다.
        self._send_to_nickname(
            prev_owner, make(MSG_NOTE_DELETED, id=note_id))
        self._send_to_nickname(
            new_owner, make(MSG_NOTE_CREATED, note=note_dict))

    def _broadcast_for_owner(self, msg: Message, *,
                              private_owner: str | None,
                              exclude: _Session | None = None) -> None:
        """``private_owner`` 가 ``None`` 이면 공개 항목으로 보고 모든 세션에 보낸다."""
        if private_owner is None:
            self._broadcast(msg, exclude=exclude)
            return
        for s in self._sessions.values():
            if s is exclude or not s.hello_received:
                continue
            if s.nickname != private_owner:
                continue
            self._send_to(s, msg)
        if (self._local is not None and self._local is not exclude
                and self._local.nickname == private_owner):
            self._send_to(self._local, msg)

    def _effective_owner_for_note(self, note: Note) -> str | None:
        """비공개 폴더 안의 메모는 자기 플래그와 무관하게 폴더의 소유자를 상속한다."""
        if note.private_owner:
            return note.private_owner
        if note.folder_id:
            folder = self.repo.get_folder(note.folder_id)
            if folder and folder.private_owner:
                return folder.private_owner
        return None

    def _broadcast_for_note(self, note_id: str, msg: Message, *,
                             exclude: _Session | None = None) -> None:
        note = self.repo.get_note(note_id)
        owner = self._effective_owner_for_note(note) if note else None
        self._broadcast_for_owner(msg, private_owner=owner, exclude=exclude)

    def _visible_notes_for(self, nickname: str) -> list[Note]:
        return [n for n in self.repo.list_notes()
                if self._effective_owner_for_note(n) in (None, nickname)]

    def _visible_folders_for(self, nickname: str) -> list[Folder]:
        return [f for f in self.repo.list_folders()
                if f.private_owner in (None, nickname)]

    def _current_users(self) -> list[str]:
        users = [s.nickname for s in self._sessions.values() if s.hello_received]
        if self._local:
            users.append(self._local.nickname)
        return users

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
        elif t == MSG_SET_NOTE_FOLDER:
            self._handle_set_folder(session, d.get("id", ""),
                                     d.get("folder_id"))
        elif t == MSG_SET_NOTE_PRIVACY:
            self._handle_set_privacy(session, d.get("id", ""),
                                      bool(d.get("private", False)))
        elif t == MSG_CREATE_FOLDER:
            self._handle_folder_create(session, d)
        elif t == MSG_UPDATE_FOLDER:
            self._handle_folder_update(session, d)
        elif t == MSG_DELETE_FOLDER:
            self._handle_folder_delete(session, d.get("id", ""))
        elif t == MSG_GET_HISTORY:
            self._handle_get_history(session, d.get("note_id"))

    def _handle_hello(self, session: _Session, nickname: str) -> None:
        session.nickname = nickname or "anon"
        session.hello_received = True
        notes = [n.to_dict() for n in self._visible_notes_for(session.nickname)]
        folders = [f.to_dict()
                   for f in self._visible_folders_for(session.nickname)]
        welcome = make(
            MSG_WELCOME,
            heartbeat_ms=self.heartbeat_ms,
            notes=notes,
            folders=folders,
            locks=self.locks.snapshot(),
            users=self._current_users(),
            host=self.host_nickname,
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
        # 정상 클라이언트는 타인의 비공개 메모를 요청하지 않지만 위변조에 대비해 차단한다.
        owner = self._effective_owner_for_note(note)
        if owner and owner != session.nickname:
            self._send_to(session, make(MSG_LOCK_DENIED, note_id=note_id,
                                         holder="", reason="forbidden"))
            return
        granted, holder = self.locks.acquire(note_id, session.nickname)
        if granted:
            self.history.begin_session(note, session.nickname)
            self._send_to(session, make(MSG_LOCK_GRANTED, note_id=note_id))
            self._broadcast_for_note(
                note_id,
                make(MSG_LOCK_HELD, note_id=note_id,
                     holder=session.nickname),
                exclude=session)
        else:
            self._send_to(session, make(MSG_LOCK_DENIED, note_id=note_id,
                                         holder=holder or ""))

    def _handle_release(self, session: _Session, note_id: str) -> None:
        note = self.repo.get_note(note_id)
        if note is not None:
            entry = self.history.end_session(note, session.nickname)
            if entry is not None:
                self._broadcast_for_note(
                    note_id,
                    make(MSG_HISTORY_APPENDED, entry=entry.to_dict()))
        if self.locks.release(note_id, session.nickname):
            self._broadcast_for_note(
                note_id, make(MSG_LOCK_RELEASED, note_id=note_id))

    def _handle_create(self, session: _Session, d: dict) -> None:
        note = Note.new(
            user=session.nickname,
            color=d.get("color"),
            folder_id=d.get("folder_id") or None,
            private_owner=d.get("private_owner") or None,
        )
        if "id" in d and d["id"]:
            note.id = d["id"]
        note.width = int(d.get("width", note.width))
        note.height = int(d.get("height", note.height))
        self.repo.insert_note(note)
        entry = self.history.record_create(note, session.nickname)
        self._broadcast_for_note(
            note.id, make(MSG_NOTE_CREATED, note=note.to_dict()))
        self._broadcast_for_note(
            note.id, make(MSG_HISTORY_APPENDED, entry=entry.to_dict()))

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
        self._broadcast_for_note(
            updated.id, make(MSG_NOTE_UPDATED, note=updated.to_dict()))

    def _handle_delete(self, session: _Session, note_id: str) -> None:
        holder = self.locks.holder(note_id)
        if holder and holder != session.nickname:
            self._send_to(session, make(MSG_ERROR,
                message=f"note locked by {holder}"))
            return
        existing = self.repo.get_note(note_id)
        if existing is None or existing.deleted:
            return
        # soft-delete 가 소유자를 지우기 전에 캡처해야 삭제 이벤트를 원래 청중에게 보낼 수 있다.
        owner = self._effective_owner_for_note(existing)
        entry = self.history.record_delete(existing, session.nickname)
        self.repo.soft_delete_note(note_id, session.nickname)
        self.locks.release(note_id, session.nickname)
        self._broadcast_for_owner(
            make(MSG_NOTE_DELETED, id=note_id), private_owner=owner)
        self._broadcast_for_owner(
            make(MSG_HISTORY_APPENDED, entry=entry.to_dict()),
            private_owner=owner)

    def _handle_set_folder(self, session: _Session, note_id: str,
                            folder_id: str | None) -> None:
        existing = self.repo.get_note(note_id)
        if existing is None or existing.deleted:
            return
        owner = self._effective_owner_for_note(existing)
        if owner and owner != session.nickname:
            self._send_to(session, make(MSG_ERROR,
                message="not allowed"))
            return
        target_folder = (self.repo.get_folder(folder_id)
                         if folder_id else None)
        if folder_id and (target_folder is None or target_folder.deleted):
            return
        if (target_folder and target_folder.private_owner
                and target_folder.private_owner != session.nickname):
            self._send_to(session, make(MSG_ERROR,
                message="cannot move into another user's private folder"))
            return
        updated = self.repo.set_note_folder(
            note_id, folder_id, session.nickname)
        if updated is None:
            return
        # 비공개 폴더로 들어가거나 나오면 메모의 실효 소유자가 뒤집힐 수 있다.
        new_owner = self._effective_owner_for_note(updated)
        self._propagate_audience_change(
            note_id, updated.to_dict(),
            prev_owner=owner, new_owner=new_owner)

    def _handle_set_privacy(self, session: _Session, note_id: str,
                             private: bool) -> None:
        existing = self.repo.get_note(note_id)
        if existing is None or existing.deleted:
            return
        owner = self._effective_owner_for_note(existing)
        # 이미 비공개인 메모는 소유자만 바꿀 수 있으나 공개 메모는 누구든 비공개로 전환할 수 있다.
        if owner and owner != session.nickname:
            self._send_to(session, make(MSG_ERROR, message="not allowed"))
            return
        new_owner_value = session.nickname if private else None
        updated = self.repo.set_note_private_owner(
            note_id, new_owner_value, session.nickname)
        if updated is None:
            return
        new_effective = self._effective_owner_for_note(updated)
        self._propagate_audience_change(
            note_id, updated.to_dict(),
            prev_owner=owner, new_owner=new_effective)

    def _handle_folder_create(self, session: _Session, d: dict) -> None:
        private_owner = session.nickname if d.get("private") else None
        folder = Folder.new(
            user=session.nickname,
            name=str(d.get("name") or "새 폴더"),
            color=d.get("color"),
            private_owner=private_owner,
        )
        if d.get("id"):
            folder.id = str(d["id"])
        self.repo.insert_folder(folder)
        self._broadcast_for_owner(
            make(MSG_FOLDER_CREATED, folder=folder.to_dict()),
            private_owner=private_owner)

    def _handle_folder_update(self, session: _Session, d: dict) -> None:
        folder_id = str(d.get("id") or "")
        existing = self.repo.get_folder(folder_id) if folder_id else None
        if existing is None or existing.deleted:
            return
        if (existing.private_owner
                and existing.private_owner != session.nickname):
            self._send_to(session, make(MSG_ERROR, message="not allowed"))
            return
        # ``private`` 는 3상태다. 키가 없으면 프라이버시를 그대로 두고, 있으면 그 값으로 갱신한다.
        kwargs: dict = {}
        if "name" in d:
            kwargs["name"] = str(d["name"])
        if "color" in d:
            kwargs["color"] = str(d["color"])
        if "private" in d:
            kwargs["private_owner"] = (
                session.nickname if d["private"] else None)
        updated = self.repo.update_folder(folder_id, **kwargs)
        if updated is None:
            return
        # 폴더 프라이버시가 바뀌면 폴더를 상속한 메모의 가시성도 바뀌므로 함께 재브로드캐스트한다.
        prev_owner = existing.private_owner
        next_owner = updated.private_owner
        if prev_owner == next_owner:
            self._broadcast_for_owner(
                make(MSG_FOLDER_UPDATED, folder=updated.to_dict()),
                private_owner=next_owner)
        else:
            self._broadcast_for_owner(
                make(MSG_FOLDER_DELETED, id=folder_id),
                private_owner=prev_owner)
            self._broadcast_for_owner(
                make(MSG_FOLDER_CREATED, folder=updated.to_dict()),
                private_owner=next_owner)
            for note in self.repo.list_notes_in_folder(folder_id):
                eff = self._effective_owner_for_note(note)
                self._broadcast_for_owner(
                    make(MSG_NOTE_DELETED, id=note.id),
                    private_owner=prev_owner)
                self._broadcast_for_owner(
                    make(MSG_NOTE_CREATED, note=note.to_dict()),
                    private_owner=eff)

    def _handle_folder_delete(self, session: _Session,
                               folder_id: str) -> None:
        existing = self.repo.get_folder(folder_id)
        if existing is None or existing.deleted:
            return
        if (existing.private_owner
                and existing.private_owner != session.nickname):
            self._send_to(session, make(MSG_ERROR, message="not allowed"))
            return
        # 메모가 폴더에서 분리되기 전에 목록을 캡처해야 새 가시성으로 다시 브로드캐스트할 수 있다.
        contained = self.repo.list_notes_in_folder(folder_id)
        prev_owner = existing.private_owner
        deleted_folder = self.repo.soft_delete_folder(folder_id)
        if deleted_folder is None:
            return
        self._broadcast_for_owner(
            make(MSG_FOLDER_DELETED, id=folder_id),
            private_owner=prev_owner)
        # 비공개 폴더에서 프라이버시를 상속하던 메모는 이제 자기 private_owner 만 따른다.
        for note in contained:
            refreshed = self.repo.get_note(note.id)
            if refreshed is None:
                continue
            new_eff = self._effective_owner_for_note(refreshed)
            if prev_owner == new_eff:
                self._broadcast_for_owner(
                    make(MSG_NOTE_UPDATED, note=refreshed.to_dict()),
                    private_owner=new_eff)
            else:
                self._broadcast_for_owner(
                    make(MSG_NOTE_DELETED, id=refreshed.id),
                    private_owner=prev_owner)
                self._broadcast_for_owner(
                    make(MSG_NOTE_CREATED, note=refreshed.to_dict()),
                    private_owner=new_eff)

    def _handle_get_history(self, session: _Session, note_id: str | None) -> None:
        visible_ids = {n.id
                       for n in self._visible_notes_for(session.nickname)}
        # soft-delete 된 메모도 포함하지 않으면 그 삭제 이력이 사라진다.
        for n in self.repo.list_notes(include_deleted=True):
            if n.deleted and self._effective_owner_for_note(n) in (
                    None, session.nickname):
                visible_ids.add(n.id)
        entries = []
        for e in self.repo.list_history(note_id):
            if e.note_id in visible_ids:
                entries.append(e.to_dict())
        self._send_to(session, make(MSG_HISTORY_LIST,
                                     note_id=note_id or "",
                                     entries=entries))

    def _on_heartbeat(self) -> None:
        self._broadcast(make(MSG_PING, ts=now_ms()))

    def _on_idle_reap(self) -> None:
        for nid in self.locks.reap_idle():
            # 편집 세션은 정리하지 않고 남겨 둔다. 다음 acquire 의 begin_session 이 덮어쓴다.
            self._broadcast(make(MSG_LOCK_RELEASED, note_id=nid))
