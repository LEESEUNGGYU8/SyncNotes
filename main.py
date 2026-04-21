from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from app import config
from app.database import SqliteRepository
from app.local_state import LocalStateStore
from app.network.guest_client import GuestClient
from app.network.host_client import HostLocalClient
from app.network.host_server import HostServer
from app.sync.history_tracker import HistoryTracker
from app.sync.lock_manager import LockManager
from app.ui import theme
from app.ui.connect_dialog import ConnectDialog
from app.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(config.APP_NAME)
    app.setOrganizationName(config.APP_NAME)
    app.setQuitOnLastWindowClosed(False)

    font_family = theme.load_application_font(config.FONT_PATH)
    theme.apply_theme(app, font_family)
    if config.ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(config.ICON_PATH)))

    local_store = LocalStateStore()

    dlg = ConnectDialog(
        last_nickname=local_store.state.nickname,
        last_ip=local_store.state.last_host_ip,
        last_port=local_store.state.last_host_port,
    )
    if dlg.exec() != QDialog.Accepted:
        return 0
    choice = dlg.choice()
    if choice is None:
        return 0

    local_store.state.nickname = choice.nickname

    if choice.mode == "host":
        repo = SqliteRepository(config.default_db_path())
        locks = LockManager(idle_timeout_ms=config.LOCK_IDLE_TIMEOUT_MS)
        history = HistoryTracker(repo)
        server = HostServer(
            repo=repo, lock_manager=locks, history_tracker=history,
            host_nickname=choice.nickname, heartbeat_ms=choice.heartbeat_ms,
        )
        if not server.start(choice.port):
            QMessageBox.critical(None, "시작 실패",
                                 f"포트 {choice.port}에서 서버를 시작할 수 없습니다.")
            return 1
        client = HostLocalClient(server=server, nickname=choice.nickname)
        client.start()
        window = MainWindow(client=client, local_state=local_store, role="호스트")

        def _shutdown():
            server.stop()
            repo.close()
            local_store.save()

        app.aboutToQuit.connect(_shutdown)
    else:
        local_store.state.last_host_ip = choice.host_ip
        local_store.state.last_host_port = choice.port
        local_store.save()
        client = GuestClient(choice.host_ip, choice.port, choice.nickname)
        window = MainWindow(client=client, local_state=local_store, role="게스트")
        client.start()

        app.aboutToQuit.connect(lambda: (client.stop(), local_store.save()))

    app.setQuitOnLastWindowClosed(True)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
