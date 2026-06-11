from __future__ import annotations

import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from app import config, i18n
from app.backup import BackupManager
from app.database import SqliteRepository
from app.ipc import IpcReceiver, forward_command
from app.local_state import LocalStateStore
from app.network.guest_client import GuestClient
from app.network.host_client import HostLocalClient
from app.network.host_server import HostServer
from app.settings import AppSettings, get_windows_autostart, set_windows_autostart
from app.sync.history_tracker import HistoryTracker
from app.sync.lock_manager import LockManager
from app.ui import theme
from app.ui.connect_dialog import ConnectDialog, ConnectionChoice
from app.ui.main_window import MainWindow
from app.ui.update_dialog import UpdateAvailableDialog
from app.updater import (
    UpdateChecker, UpdateDownloader, launch_installer,
)
from app.win_jumplist import register as register_jumplist, set_app_user_model_id


# 점프리스트의 "새 메모" 항목이 새 프로세스를 띄울 때 넘기는 CLI 플래그.
NEW_NOTE_FLAG = "--new-note"


def _sync_autostart(settings: AppSettings) -> None:
    actual = get_windows_autostart()
    if settings.autostart and not actual:
        set_windows_autostart(True)
    elif not settings.autostart and actual:
        settings.autostart = True


def _saved_choice(local_store: LocalStateStore) -> ConnectionChoice | None:
    """저장해 둔 직전 접속 정보를 복원한다. 값이 있으면 다음 실행에서
    접속 다이얼로그를 건너뛰고 자동으로 접속한다."""
    ls = local_store.state
    if ls.last_mode == "host" and ls.nickname:
        return ConnectionChoice(
            mode="host",
            nickname=ls.nickname,
            port=ls.last_host_port or config.DEFAULT_PORT,
            heartbeat_ms=ls.last_heartbeat_ms or config.DEFAULT_HEARTBEAT_MS,
        )
    if ls.last_mode == "guest" and ls.nickname:
        return ConnectionChoice(
            mode="guest",
            nickname=ls.nickname,
            port=ls.last_host_port or config.DEFAULT_PORT,
            host_ip=ls.last_host_ip or "127.0.0.1",
        )
    return None


def _prompt_for_choice(local_store: LocalStateStore,
                       settings: AppSettings) -> ConnectionChoice | None:
    ls = local_store.state
    dlg = ConnectDialog(
        last_nickname=ls.nickname,
        last_ip=ls.last_host_ip,
        last_port=ls.last_host_port or settings.default_port,
    )
    if dlg.exec() != QDialog.Accepted:
        return None
    return dlg.choice()


def _persist_choice(local_store: LocalStateStore,
                    choice: ConnectionChoice) -> None:
    """현재 접속 정보를 저장한다. 다음 실행 때 자동 재접속에 쓰인다."""
    ls = local_store.state
    ls.last_mode = choice.mode
    ls.nickname = choice.nickname
    ls.last_host_port = choice.port
    if choice.mode == "host":
        ls.last_heartbeat_ms = choice.heartbeat_ms
    else:
        ls.last_host_ip = choice.host_ip
    local_store.save()


def main() -> int:
    want_new_note = NEW_NOTE_FLAG in sys.argv

    # 이번 실행의 목적이 점프리스트 명령 전달뿐이면, 이미 떠 있는 인스턴스에 넘기고 바로 종료한다.
    # 실행 중인 인스턴스가 없으면 본 프로세스가 정상 부팅한 뒤 welcome 직후에 직접 처리한다.
    if want_new_note and forward_command("new-note"):
        return 0

    # 창이 표시되기 전에 호출해야 작업 표시줄이 본 프로세스를 AppUserModelID로 그룹화하고,
    # 뒤이어 등록하는 점프리스트가 앱 아이콘에 제대로 붙는다.
    set_app_user_model_id()

    app = QApplication(sys.argv)
    app.setApplicationName(config.APP_NAME)
    app.setOrganizationName(config.APP_NAME)
    app.setQuitOnLastWindowClosed(False)

    settings = AppSettings.load()

    # 언어를 가장 먼저 확정한다.
    # 폰트 family 선택(일본어→Pretendard JP)과 이후 만들어질 모든 위젯의 텍스트가 이 값에 의존하기 때문이다.
    # 최초 실행이면 OS 로케일을 감지해 그 결과를 설정에 저장해 둔다.
    language = i18n.resolve_language(settings.language_code)
    i18n.set_language(language)
    if not settings.language_code:
        settings.language_code = language

    font_family = theme.load_application_fonts(language)
    theme.apply_theme(app, font_family)
    app_icon = QIcon(str(config.ICON_PATH)) if config.ICON_PATH.exists() else QIcon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    _sync_autostart(settings)
    settings.save()

    local_store = LocalStateStore()

    backup_manager: BackupManager | None = None

    # 저장된 접속 정보가 있으면 다이얼로그 없이 자동 접속한다. 호스트로
    # 시작하다가 포트 바인딩에 실패하면 저장된 역할을 비우고 다시 시도한다.

    while True:
        choice = _saved_choice(local_store)
        if choice is None:
            choice = _prompt_for_choice(local_store, settings)
            if choice is None:
                return 0

        if choice.mode == "host":
            db_path = config.default_db_path()
            repo = SqliteRepository(db_path)
            locks = LockManager(idle_timeout_ms=config.LOCK_IDLE_TIMEOUT_MS)
            history = HistoryTracker(repo)
            server = HostServer(
                repo=repo, lock_manager=locks, history_tracker=history,
                host_nickname=choice.nickname, heartbeat_ms=choice.heartbeat_ms,
            )
            if not server.start(choice.port):
                repo.close()
                QMessageBox.critical(
                    None, i18n.t("boot.start_failed_title"),
                    i18n.t("boot.port_bind_failed", port=choice.port))
                # 저장된 역할을 비워 다음 루프에서 다이얼로그가 다시 뜨게 한다.
                local_store.state.last_mode = ""
                local_store.save()
                continue
            _persist_choice(local_store, choice)
            client = HostLocalClient(server=server, nickname=choice.nickname)
            # 중요: client.start() 이전에 MainWindow를 먼저 만들어야 한다.
            # 그래야 초기 welcome(저장된 메모 포함)이 도착할 때 시그널 구독이 이미 연결돼 있다.
            window = MainWindow(client=client, local_state=local_store,
                                role="host", settings=settings, app_icon=app_icon)
            client.start()
            backup_manager = BackupManager(db_path=db_path, settings=settings)

            def _on_backup_now():
                dest = backup_manager.run_backup()
                if dest is not None:
                    QMessageBox.information(
                        window, i18n.t("boot.backup_done_title"),
                        i18n.t("boot.backup_done_body", dest=dest))

            window.backupRequested.connect(_on_backup_now)

            def _shutdown():
                try:
                    window._flush_pending_edits()
                    # 모든 메모를 teardown 모드로 표시해 둔다.
                    # Windows 세션 종료 흐름에서 Qt가 각 창에 closeEvent를 보내더라도,
                    # hideRequested가 발화돼 local_state가 hidden으로 오염되는 것을 막는다.
                    window._teardown_stickies()
                except Exception:
                    pass
                if backup_manager is not None:
                    backup_manager.stop()
                server.stop()
                repo.close()
                local_store.save()
                settings.save()

            app.aboutToQuit.connect(_shutdown)
            break
        else:  # guest
            _persist_choice(local_store, choice)
            client = GuestClient(choice.host_ip, choice.port, choice.nickname)
            # 호스트와 같은 이유로 MainWindow를 먼저 만들어 시그널을 구독한 뒤 client.start()를 호출한다.
            window = MainWindow(client=client, local_state=local_store,
                                role="guest", settings=settings, app_icon=app_icon)
            client.start()

            def _shutdown_guest():
                try:
                    window._flush_pending_edits()
                    # 호스트의 _shutdown과 같은 이유로, 자동 실행이나 세션 종료 사이클에서 메모 가시성이 의도와 다르게 바뀌지 않게 한다.
                    window._teardown_stickies()
                except Exception:
                    pass
                client.stop()
                local_store.save()
                settings.save()

            app.aboutToQuit.connect(_shutdown_guest)
            break

    app.setQuitOnLastWindowClosed(True)
    window.show()

    # 작업 표시줄 점프리스트 명령을 위한 단일 인스턴스 IPC.
    # 사용자별 파이프를 먼저 잡은 프로세스가 이후의 '--new-note'를 처리한다.
    # 동시에 떠 있는 다른 인스턴스는 바인딩만 실패한 채 평소대로 동작한다.
    ipc = IpcReceiver(app)
    if ipc.listen():
        ipc.commandReceived.connect(window.handle_ipc_command)

    # 점프리스트는 매 실행마다 다시 등록한다. 비용이 작고 멱등이며,
    # exe 경로를 sys.executable로 두면 frozen·dev 모두 자기 자신을 실행한다.
    register_jumplist(exe_path=sys.executable)

    # 본 프로세스가 --new-note로 직접 실행된 경우(전달할 인스턴스가 없었을 때),
    # welcome 스냅샷을 받은 뒤에 메모를 만든다.
    # 그 전에 호출하면 클라이언트가 아직 연결되지 않아 create_note가 무산된다.
    if want_new_note:
        def _create_after_welcome(_data=None):
            try:
                client.welcomed.disconnect(_create_after_welcome)
            except (RuntimeError, TypeError):
                pass
            QTimer.singleShot(0, window.handle_new_note_request)
        client.welcomed.connect(_create_after_welcome)

    # 자동 업데이트 확인은 시작 5초 후에 동작한다.
    # welcome 핸드셰이크와 UI가 안정된 뒤에 수행하려는 목적이다.
    # 네트워크 오류는 조용히 무시하고, 새 버전이 있을 때만 다이얼로그를 띄운다.
    _schedule_update_check(app, window)

    return app.exec()


def _schedule_update_check(app: QApplication, window: MainWindow) -> None:
    def _begin_check():
        checker = UpdateChecker(config.APP_VERSION, parent=app)

        def _on_available(info: dict):
            _prompt_and_install(app, window, info)

        def _on_error(_msg: str):
            # 네트워크 오류는 흔하다(오프라인, rate-limit 등).
            # 사용자에게 노출하지 않는다.
            pass

        checker.updateAvailable.connect(_on_available)
        checker.upToDate.connect(lambda: None)
        checker.error.connect(_on_error)
        checker.check()

    QTimer.singleShot(5000, _begin_check)


def _prompt_and_install(app: QApplication, window: MainWindow,
                         info: dict) -> None:
    """업데이트 알림 다이얼로그를 띄운다.
    사용자가 수락하면 다운로드 → 무결성 검증 → 인스톨러 실행까지 진행한다."""
    dlg = UpdateAvailableDialog(
        current_version=config.APP_VERSION,
        info=info,
        parent=window,
    )
    if dlg.exec() != QDialog.Accepted:
        return

    progress = QMessageBox(window)
    progress.setIcon(QMessageBox.Information)
    progress.setWindowTitle(i18n.t("boot.update_downloading_title"))
    progress.setStandardButtons(QMessageBox.NoButton)
    progress.setText(i18n.t("boot.update_downloading_body"))
    progress.show()

    downloader = UpdateDownloader(info, parent=app)

    def _on_ready(path: str):
        progress.close()
        launch_installer(path)
        # Inno Setup이 본 프로세스를 종료시키지만,
        # SmartScreen에서 사용자가 취소했을 경우를 대비해 짧게 대기 후 종료한다.
        QTimer.singleShot(200, app.quit)

    def _on_error(message: str):
        progress.close()
        QMessageBox.warning(
            window, i18n.t("boot.update_failed_title"),
            i18n.t("boot.update_failed_body", message=message))

    downloader.installerReady.connect(_on_ready)
    downloader.error.connect(_on_error)
    downloader.start()


if __name__ == "__main__":
    sys.exit(main())
