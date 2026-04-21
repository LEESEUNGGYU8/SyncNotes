from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import config


@dataclass
class ConnectionChoice:
    mode: str               # 'host' | 'guest'
    nickname: str
    port: int
    host_ip: str = ""       # guest only
    heartbeat_ms: int = config.DEFAULT_HEARTBEAT_MS  # host only


class ConnectDialog(QDialog):
    def __init__(self, last_nickname: str = "",
                 last_ip: str = "127.0.0.1",
                 last_port: int = config.DEFAULT_PORT,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("ClaudeNotes - 접속")
        self.setModal(True)

        self._tabs = QTabWidget(self)
        self._tabs.addTab(self._build_host_tab(last_nickname), "호스트")
        self._tabs.addTab(self._build_guest_tab(last_nickname, last_ip, last_port),
                          "게스트")

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self._tabs)
        layout.addWidget(buttons)
        self.setMinimumWidth(360)

        self._choice: ConnectionChoice | None = None

    def _build_host_tab(self, last_nickname: str) -> QWidget:
        w = QWidget(self)
        form = QFormLayout(w)
        self._host_nickname = QLineEdit(last_nickname or "host")
        self._host_port = QSpinBox()
        self._host_port.setRange(1, 65535)
        self._host_port.setValue(config.DEFAULT_PORT)
        self._host_heartbeat = QSpinBox()
        self._host_heartbeat.setRange(500, 60_000)
        self._host_heartbeat.setSingleStep(500)
        self._host_heartbeat.setSuffix(" ms")
        self._host_heartbeat.setValue(config.DEFAULT_HEARTBEAT_MS)
        form.addRow("닉네임", self._host_nickname)
        form.addRow("포트", self._host_port)
        form.addRow("하트비트 주기", self._host_heartbeat)
        return w

    def _build_guest_tab(self, last_nickname: str, last_ip: str,
                         last_port: int) -> QWidget:
        w = QWidget(self)
        form = QFormLayout(w)
        self._guest_nickname = QLineEdit(last_nickname or "guest")
        self._guest_ip = QLineEdit(last_ip)
        self._guest_port = QSpinBox()
        self._guest_port.setRange(1, 65535)
        self._guest_port.setValue(last_port)
        form.addRow("닉네임", self._guest_nickname)
        form.addRow("호스트 IP", self._guest_ip)
        form.addRow("포트", self._guest_port)
        return w

    def accept(self) -> None:
        if self._tabs.currentIndex() == 0:
            nick = self._host_nickname.text().strip() or "host"
            self._choice = ConnectionChoice(
                mode="host", nickname=nick,
                port=self._host_port.value(),
                heartbeat_ms=self._host_heartbeat.value(),
            )
        else:
            nick = self._guest_nickname.text().strip() or "guest"
            self._choice = ConnectionChoice(
                mode="guest", nickname=nick,
                port=self._guest_port.value(),
                host_ip=self._guest_ip.text().strip() or "127.0.0.1",
            )
        super().accept()

    def choice(self) -> ConnectionChoice | None:
        return self._choice
