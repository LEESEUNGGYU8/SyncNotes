from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import config, i18n
from .theme import refresh_style


@dataclass
class ConnectionChoice:
    mode: str               # 'host' | 'guest'
    nickname: str
    port: int
    host_ip: str = ""
    heartbeat_ms: int = config.DEFAULT_HEARTBEAT_MS


class _RoleButton(QPushButton):
    def __init__(self, title: str, subtitle: str):
        super().__init__()
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self._title = title
        self._subtitle = subtitle
        self.setMinimumHeight(64)
        self.setStyleSheet("""
            QPushButton {
                text-align: left;
                background: #F5F5F5;
                color: #1F1F1F;
                border: 1px solid #EAEAEA;
                border-radius: 10px;
                padding: 10px 14px;
                font-weight: 600;
            }
            QPushButton:hover { background: #EBEBEB; }
            QPushButton:checked {
                background: #1F1F1F;
                color: white;
                border-color: #1F1F1F;
            }
        """)
        self.setText(f"{title}\n{subtitle}")


class ConnectDialog(QDialog):
    def __init__(self, last_nickname: str = "",
                 last_ip: str = "127.0.0.1",
                 last_port: int = config.DEFAULT_PORT,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(i18n.t("connect.window_title", app=config.APP_NAME))
        self.setModal(True)
        self.setMinimumWidth(380)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 16)
        root.setSpacing(14)

        title = QLabel(i18n.t("connect.choose_mode"))
        title.setProperty("role", "title")
        root.addWidget(title)

        self._btn_host = _RoleButton(i18n.t("connect.role_host_title"),
                                      i18n.t("connect.role_host_subtitle"))
        self._btn_guest = _RoleButton(i18n.t("connect.role_guest_title"),
                                       i18n.t("connect.role_guest_subtitle"))
        self._btn_host.setChecked(True)
        self._btn_host.clicked.connect(lambda: self._set_mode(0))
        self._btn_guest.clicked.connect(lambda: self._set_mode(1))

        role_row = QHBoxLayout()
        role_row.setSpacing(10)
        role_row.addWidget(self._btn_host, 1)
        role_row.addWidget(self._btn_guest, 1)
        root.addLayout(role_row)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_host_form(last_nickname))
        self._stack.addWidget(self._build_guest_form(
            last_nickname, last_ip, last_port))
        root.addWidget(self._stack)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        buttons.button(QDialogButtonBox.Ok).setText(i18n.t("connect.btn_start"))
        cancel_btn = buttons.button(QDialogButtonBox.Cancel)
        cancel_btn.setText(i18n.t("connect.btn_cancel"))
        cancel_btn.setProperty("secondary", True)
        refresh_style(cancel_btn)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._choice: ConnectionChoice | None = None

    def _set_mode(self, idx: int) -> None:
        self._btn_host.setChecked(idx == 0)
        self._btn_guest.setChecked(idx == 1)
        self._stack.setCurrentIndex(idx)

    def _build_host_form(self, last_nickname: str) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(0, 6, 0, 0)
        form.setSpacing(10)
        self._host_nickname = QLineEdit(last_nickname or "host")
        self._host_port = QSpinBox()
        self._host_port.setRange(1, 65535)
        self._host_port.setValue(config.DEFAULT_PORT)
        self._host_heartbeat = QSpinBox()
        self._host_heartbeat.setRange(500, 60_000)
        self._host_heartbeat.setSingleStep(500)
        self._host_heartbeat.setSuffix(" ms")
        self._host_heartbeat.setValue(config.DEFAULT_HEARTBEAT_MS)
        form.addRow(i18n.t("connect.field_nickname"), self._host_nickname)
        form.addRow(i18n.t("connect.field_port"), self._host_port)
        form.addRow(i18n.t("connect.field_heartbeat"), self._host_heartbeat)
        return w

    def _build_guest_form(self, last_nickname: str, last_ip: str,
                         last_port: int) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(0, 6, 0, 0)
        form.setSpacing(10)
        self._guest_nickname = QLineEdit(last_nickname or "guest")
        self._guest_ip = QLineEdit(last_ip)
        self._guest_port = QSpinBox()
        self._guest_port.setRange(1, 65535)
        self._guest_port.setValue(last_port)
        form.addRow(i18n.t("connect.field_nickname"), self._guest_nickname)
        form.addRow(i18n.t("connect.field_host_ip"), self._guest_ip)
        form.addRow(i18n.t("connect.field_port"), self._guest_port)
        return w

    def accept(self) -> None:
        if self._stack.currentIndex() == 0:
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
