"""단일 인스턴스 IPC.

명명된 로컬 서버를 가장 먼저 바인딩한 프로세스가 점프리스트 명령의 수신자가 되고,
이후 실행된 프로세스('--new-note' 등)는 명령을 그쪽으로 넘기고 종료한다.
바인딩에 실패한 나머지 인스턴스도 평소대로 동작한다."""
from __future__ import annotations

import getpass

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket


def ipc_name() -> str:
    """다른 Windows 계정과 충돌하지 않도록 사용자별 파이프 이름을 만든다."""
    try:
        user = getpass.getuser() or "default"
    except Exception:
        user = "default"
    # Windows 명명된 파이프는 경로 문자에 민감하므로 안전한 문자만 남긴다.
    safe = "".join(ch if ch.isalnum() else "_" for ch in user)
    return f"SyncNotes-IPC-{safe}"


def forward_command(command: str, timeout_ms: int = 500) -> bool:
    """이미 실행 중인 인스턴스에 ``command`` 를 전달한다.

    아무도 듣고 있지 않으면 False를 돌려주며, 이때 호출 측은 정상 부팅을 이어가면 된다."""
    socket = QLocalSocket()
    socket.connectToServer(ipc_name())
    if not socket.waitForConnected(timeout_ms):
        return False
    payload = (command + "\n").encode("utf-8")
    socket.write(payload)
    socket.flush()
    socket.waitForBytesWritten(timeout_ms)
    socket.disconnectFromServer()
    return True


class IpcReceiver(QObject):
    commandReceived = Signal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._on_new_connection)
        self._is_owner = False

    def listen(self) -> bool:
        """IPC 이름을 잡아 명령 수신자가 되면 True를 반환한다."""
        name = ipc_name()
        # 이전 프로세스가 비정상 종료하며 남긴 stale 핸들을 정리한 뒤 다시 시도한다.
        if not self._server.listen(name):
            QLocalServer.removeServer(name)
            if not self._server.listen(name):
                return False
        self._is_owner = True
        return True

    def stop(self) -> None:
        self._server.close()

    def is_owner(self) -> bool:
        return self._is_owner

    def _on_new_connection(self) -> None:
        while True:
            sock = self._server.nextPendingConnection()
            if sock is None:
                return
            sock.readyRead.connect(lambda s=sock: self._on_ready_read(s))
            sock.disconnected.connect(sock.deleteLater)

    def _on_ready_read(self, sock: QLocalSocket) -> None:
        data = bytes(sock.readAll()).decode("utf-8", errors="ignore")
        for line in data.splitlines():
            line = line.strip()
            if line:
                self.commandReceived.emit(line)
