from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor, QIcon, QKeySequence, QMouseEvent, QPainter, QPen,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStatusBar,
    QSystemTrayIcon,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import config, datetime_fmt, i18n
from ..local_state import LocalStateStore
from ..network.client_base import ClientBase
from ..settings import AppSettings
from .folder_dialog import FolderEditDialog
from .history_viewer import HistoryViewer
from .icons import color_swatch_icon, svg_icon
from .menu_item import add_centered_menu_action
from .rich_text import has_non_checkbox_image, html_to_plain
from .sessions_dialog import SessionsDialog
from .settings_dialog import SettingsDialog
from .sticky_note import StickyNoteWidget
from .theme import RoundedScrollBar


# 실제 폴더 id 와 같은 dict 키 자리에 분기 없이 섞여 저장되도록 문자열 sentinel 로 둔다.
FOLDER_ALL = "__all__"
FOLDER_NONE = "__none__"


# Windows 11 다크 모드에서 QMenu 항목이 전역 QSS 를 무시하고 네이티브 다크
# 팔레트로 렌더링되는 경우가 있어, 팝업마다 이 스타일을 다시 적용해 라이트 톤을 강제한다.
_LIGHT_MENU_QSS = (
    "QMenu { background-color: #FFFFFF; border: 1px solid #EAEAEA; "
    "border-radius: 8px; padding: 4px; color: #1F1F1F; }"
    "QMenu::item { background-color: transparent; "
    "padding: 6px 22px 6px 14px; border-radius: 6px; "
    "color: #1F1F1F; min-width: 130px; }"
    "QMenu::item:selected { background-color: #F0F0F0; color: #1F1F1F; }"
    "QMenu::item:disabled { color: #A0A0A0; background-color: transparent; }"
    "QMenu::separator { height: 1px; background: #EAEAEA; "
    "margin: 4px 6px; }"
)


def _local_lan_ip() -> str:
    """이 PC 의 LAN 주소를 best-effort 로 찾아낸다.

    UDP connect 는 패킷을 보내지 않지만 OS 가 송신 인터페이스를 고르게
    하므로, 그 소스 IP 가 LAN 에서 보이는 주소가 된다. 인터페이스가
    없으면 loopback 으로 폴백한다."""
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.settimeout(0)
        sock.connect(("10.255.255.255", 1))
        return sock.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        sock.close()


class MainWindow(QMainWindow):
    backupRequested = Signal()

    def __init__(self, client: ClientBase, local_state: LocalStateStore,
                 role: str, settings: AppSettings | None = None,
                 app_icon: QIcon | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{config.APP_NAME}")
        self.resize(380, 600)
        if app_icon is not None and not app_icon.isNull():
            self.setWindowIcon(app_icon)

        self._client = client
        self._local = local_state
        self._role = role
        self._settings = settings or AppSettings()
        self._app_icon = app_icon
        self._notes: dict[str, dict[str, Any]] = {}
        self._folders: dict[str, dict[str, Any]] = {}
        self._current_folder: str = FOLDER_ALL
        self._locks: dict[str, str] = {}
        self._stickies: dict[str, StickyNoteWidget] = {}
        self._cards: dict[str, _NoteCard] = {}
        self._users: list[str] = []
        self._history_viewer: HistoryViewer | None = None
        self._sessions_dialog: SessionsDialog | None = None
        # 호스트는 첫 welcome 이전부터 자기 닉네임이 호스트 닉네임임을 알므로 미리 채운다.
        self._host_nickname: str = (
            client.nickname() if role == "host" else "")
        self._connected: bool = False
        self._heartbeat_ms: int = 0
        self._force_quit = False
        self._tray: QSystemTrayIcon | None = None
        self._search_query: str = ""
        # 복원이 일반 lock → update → release 흐름을 타야 이력 항목이 남으므로,
        # 클릭 시 여기에 내용을 담아 두고 _on_lock_granted 에서 소비한다.
        self._pending_restore: dict[str, str] = {}
        self._selection_mode: bool = False
        self._selected_notes: set[str] = set()
        self._selection_anchor: str | None = None

        self._build_ui()
        self._wire_client()
        self._build_tray()

    def _build_ui(self) -> None:
        root = QWidget(self)
        root.setObjectName("ContentRoot")
        self.setCentralWidget(root)

        v = QVBoxLayout(root)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        top = QWidget()
        top_row = QHBoxLayout(top)
        top_row.setContentsMargins(12, 12, 12, 8)
        top_row.setSpacing(8)

        self._new_btn = QPushButton(i18n.t("main.btn_new_note"))
        self._new_btn.setIcon(svg_icon("plus"))
        self._new_btn.setIconSize(QSize(16, 16))
        self._new_btn.setProperty("primary", True)
        self._new_btn.setCursor(Qt.PointingHandCursor)
        self._new_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._new_btn.setMinimumHeight(44)
        self._new_btn.clicked.connect(
            lambda: self._create_note(config.DEFAULT_COLOR))
        top_row.addWidget(self._new_btn, 1)

        self._hist_btn = QPushButton(i18n.t("main.btn_history"))
        self._hist_btn.setIcon(svg_icon("clock"))
        self._hist_btn.setIconSize(QSize(16, 16))
        self._hist_btn.setProperty("primary", True)
        self._hist_btn.setCursor(Qt.PointingHandCursor)
        self._hist_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._hist_btn.setMinimumHeight(44)
        self._hist_btn.clicked.connect(self._open_history)
        top_row.addWidget(self._hist_btn, 1)

        square_style = (
            "QToolButton { background: #F5F5F5; border: 1px solid #EAEAEA; "
            "border-radius: 10px; padding: 0; color: #1F1F1F; }"
            "QToolButton:hover { background: #F0F0F0; border-color: #D5D5D5; }"
            "QToolButton:pressed { background: #E2E2E2; }"
        )

        self._sessions_btn = QToolButton()
        self._sessions_btn.setIcon(svg_icon("users"))
        self._sessions_btn.setIconSize(QSize(16, 16))
        self._sessions_btn.setToolTip(i18n.t("main.tooltip_sessions"))
        self._sessions_btn.setCursor(Qt.PointingHandCursor)
        self._sessions_btn.setFixedSize(44, 44)
        self._sessions_btn.setStyleSheet(square_style)
        self._sessions_btn.clicked.connect(self._open_sessions)
        top_row.addWidget(self._sessions_btn)

        self._settings_btn = QToolButton()
        self._settings_btn.setIcon(svg_icon("settings"))
        self._settings_btn.setIconSize(QSize(16, 16))
        self._settings_btn.setToolTip(i18n.t("main.tooltip_settings"))
        self._settings_btn.setCursor(Qt.PointingHandCursor)
        self._settings_btn.setFixedSize(44, 44)
        self._settings_btn.setStyleSheet(square_style)
        self._settings_btn.clicked.connect(self._open_settings)
        top_row.addWidget(self._settings_btn)

        v.addWidget(top)

        search_wrap = QWidget()
        search_layout = QHBoxLayout(search_wrap)
        search_layout.setContentsMargins(12, 2, 12, 6)
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText(i18n.t("main.search_placeholder"))
        self._search_input.setClearButtonEnabled(True)
        from PySide6.QtGui import QAction
        search_action = QAction(svg_icon("search", color="#888888"),
                                 "", self._search_input)
        self._search_input.addAction(
            search_action, QLineEdit.LeadingPosition)
        self._search_input.textChanged.connect(self._apply_search_filter)
        search_layout.addWidget(self._search_input)
        v.addWidget(search_wrap)

        folder_wrap = QWidget()
        folder_row = QHBoxLayout(folder_wrap)
        folder_row.setContentsMargins(12, 0, 12, 8)
        folder_row.setSpacing(8)

        self._folder_chip = QPushButton(i18n.t("main.folder_all"))
        self._folder_chip.setIcon(svg_icon("folder", color="#3A3A3A"))
        self._folder_chip.setIconSize(QSize(16, 16))
        self._folder_chip.setCursor(Qt.PointingHandCursor)
        self._folder_chip.setMinimumHeight(34)
        self._folder_chip.setStyleSheet(
            "QPushButton { background: #F5F5F5; border: 1px solid #EAEAEA; "
            "border-radius: 10px; padding: 4px 12px; "
            "color: #1F1F1F; text-align: left; font-weight: 600; }"
            "QPushButton:hover { background: #F0F0F0; border-color: #D5D5D5; }"
        )
        self._folder_chip.clicked.connect(self._show_folder_selector)
        folder_row.addWidget(self._folder_chip, 1)

        self._folder_menu_btn = QToolButton()
        self._folder_menu_btn.setIcon(svg_icon("more"))
        self._folder_menu_btn.setIconSize(QSize(16, 16))
        self._folder_menu_btn.setToolTip(i18n.t("main.tooltip_folder_actions"))
        self._folder_menu_btn.setCursor(Qt.PointingHandCursor)
        self._folder_menu_btn.setFixedSize(34, 34)
        self._folder_menu_btn.setStyleSheet(
            "QToolButton { background: #F5F5F5; border: 1px solid #EAEAEA; "
            "border-radius: 10px; padding: 0; color: #1F1F1F; }"
            "QToolButton:hover { background: #F0F0F0; border-color: #D5D5D5; }"
        )
        self._folder_menu_btn.clicked.connect(self._show_folder_menu)
        folder_row.addWidget(self._folder_menu_btn)

        v.addWidget(folder_wrap)

        hdr_row = QWidget()
        hdr = QHBoxLayout(hdr_row)
        hdr.setContentsMargins(20, 12, 16, 8)
        hdr.setSpacing(8)
        header_lbl = QLabel(i18n.t("main.header_recent_notes"))
        header_lbl.setStyleSheet(
            "color: #111827; font-size: 14px; font-weight: 800; "
            "letter-spacing: -0.2px;")
        hdr.addWidget(header_lbl, 0)

        self._empty_hint = QLabel("")
        self._empty_hint.setStyleSheet(
            "color: #4B5563; font-size: 11px; font-weight: 700; "
            "background: rgba(17, 24, 39, 0.07); "
            "border-radius: 9px; padding: 2px 9px;")
        hdr.addWidget(self._empty_hint, 0)
        hdr.addStretch(1)

        self._select_btn = QToolButton()
        self._select_btn.setText(i18n.t("main.btn_select"))
        self._select_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self._select_btn.setCheckable(True)
        self._select_btn.setCursor(Qt.PointingHandCursor)
        self._select_btn.setFocusPolicy(Qt.NoFocus)
        self._select_btn.setStyleSheet(
            "QToolButton { background: transparent; border: 1px solid "
            "  #D5D5D5; border-radius: 7px; padding: 3px 10px; "
            "  color: #4B5563; font-size: 11.5px; font-weight: 700; }"
            "QToolButton:hover { background: #F3F4F6; }"
            "QToolButton:checked { background: #3B82F6; "
            "  border-color: #3B82F6; color: #FFFFFF; }"
        )
        self._select_btn.toggled.connect(self._on_select_mode_toggled)
        hdr.addWidget(self._select_btn)

        v.addWidget(hdr_row)

        scroll_wrap = QWidget()
        scroll_wrap_v = QVBoxLayout(scroll_wrap)
        scroll_wrap_v.setContentsMargins(12, 2, 12, 10)
        scroll_wrap_v.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.NoFrame)
        self._scroll.setVerticalScrollBar(RoundedScrollBar())
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(
            "QScrollArea { background: #FAFBFD; "
            "border: 1px solid #ECECEC; border-radius: 14px; }"
        )
        # 뷰포트를 투명으로 둬야 스크롤 영역이 그리는 둥근 배경이 드러난다.
        self._scroll.viewport().setStyleSheet("background: transparent;")
        self._scroll.viewport().setAutoFillBackground(False)

        self._cards_container = QWidget()
        self._cards_container.setObjectName("CardsContainer")
        self._cards_container.setStyleSheet("background: transparent;")
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setContentsMargins(10, 10, 10, 10)
        self._cards_layout.setSpacing(8)
        self._cards_layout.addStretch(1)

        self._scroll.setWidget(self._cards_container)
        scroll_wrap_v.addWidget(self._scroll)
        v.addWidget(scroll_wrap, 1)

        self._bulk_bar = QWidget()
        self._bulk_bar.setObjectName("BulkActionBar")
        self._bulk_bar.setStyleSheet(
            "QWidget#BulkActionBar { background: #FFFFFF; "
            "border-top: 1px solid #E5E7EB; }"
            "QWidget#BulkActionBar QLabel { color: #1F2937; "
            "font-size: 12px; font-weight: 700; }"
            "QWidget#BulkActionBar QPushButton { background: #F3F4F6; "
            "color: #1F2937; border: 1px solid #D6D8DC; "
            "border-radius: 8px; padding: 6px 12px; "
            "font-size: 11.5px; font-weight: 700; }"
            "QWidget#BulkActionBar QPushButton:hover { "
            "background: #E5E7EB; border-color: #C0C4CB; }"
            "QWidget#BulkActionBar QPushButton:disabled { "
            "color: #B0B4BA; background: #F7F7F7; "
            "border-color: #ECECEC; }"
            "QWidget#BulkActionBar QPushButton#BulkDelete { "
            "color: #B91C1C; border-color: #FAD3D3; "
            "background: #FEF2F2; }"
            "QWidget#BulkActionBar QPushButton#BulkDelete:hover { "
            "background: #FEE2E2; border-color: #F4ACAC; }"
        )
        bulk_row = QHBoxLayout(self._bulk_bar)
        bulk_row.setContentsMargins(14, 8, 14, 8)
        bulk_row.setSpacing(8)
        self._bulk_count_lbl = QLabel(i18n.t("main.bulk_selected_count", count=0))
        bulk_row.addWidget(self._bulk_count_lbl)
        bulk_row.addStretch(1)
        self._bulk_select_all_btn = QPushButton(i18n.t("main.bulk_select_all"))
        self._bulk_select_all_btn.setCursor(Qt.PointingHandCursor)
        self._bulk_select_all_btn.clicked.connect(self._bulk_select_all)
        bulk_row.addWidget(self._bulk_select_all_btn)
        self._bulk_folder_btn = QPushButton(i18n.t("main.bulk_move_folder"))
        self._bulk_folder_btn.setCursor(Qt.PointingHandCursor)
        self._bulk_folder_btn.clicked.connect(self._bulk_show_folder_menu)
        bulk_row.addWidget(self._bulk_folder_btn)
        self._bulk_private_btn = QPushButton(i18n.t("main.bulk_private"))
        self._bulk_private_btn.setCursor(Qt.PointingHandCursor)
        self._bulk_private_btn.clicked.connect(self._bulk_show_privacy_menu)
        bulk_row.addWidget(self._bulk_private_btn)
        self._bulk_delete_btn = QPushButton(i18n.t("main.bulk_delete"))
        self._bulk_delete_btn.setObjectName("BulkDelete")
        self._bulk_delete_btn.setCursor(Qt.PointingHandCursor)
        self._bulk_delete_btn.clicked.connect(self._bulk_delete)
        bulk_row.addWidget(self._bulk_delete_btn)
        self._bulk_bar.hide()
        v.addWidget(self._bulk_bar)

        status = QStatusBar()
        self.setStatusBar(status)
        self._status = status
        self._status.showMessage(i18n.t("main.status_connecting"))

        self._select_all_shortcut = QShortcut(
            QKeySequence.SelectAll, self, self._select_all_via_shortcut)

    def _wire_client(self) -> None:
        c = self._client
        c.welcomed.connect(self._on_welcomed)
        c.noteCreated.connect(self._on_note_created)
        c.noteUpdated.connect(self._on_note_updated)
        c.noteDeleted.connect(self._on_note_deleted)
        c.folderCreated.connect(self._on_folder_created)
        c.folderUpdated.connect(self._on_folder_updated)
        c.folderDeleted.connect(self._on_folder_deleted)
        c.lockGranted.connect(self._on_lock_granted)
        c.lockDenied.connect(self._on_lock_denied)
        c.lockHeld.connect(self._on_lock_held)
        c.lockReleased.connect(self._on_lock_released)
        c.userJoined.connect(self._on_user_joined)
        c.userLeft.connect(self._on_user_left)
        c.historyAppended.connect(self._on_history_appended)
        c.historyList.connect(self._on_history_list)
        c.connectionChanged.connect(self._on_connection_changed)
        c.errorOccurred.connect(self._on_error)

    def _create_note(self, color: str) -> None:
        # 전체 / 미분류 뷰에서는 폴더 없음으로, 그 외엔 현재 폴더에 넣는다.
        folder_id = (self._current_folder
                     if self._current_folder not in
                     (FOLDER_ALL, FOLDER_NONE)
                     else None)
        self._client.create_note(
            color, config.DEFAULT_NOTE_WIDTH, config.DEFAULT_NOTE_HEIGHT,
            folder_id=folder_id)

    def handle_ipc_command(self, command: str) -> None:
        """형제 프로세스가 전달한 명령 줄을 분배한다(예: 작업 표시줄
        점프리스트에서 '새 메모' 클릭)."""
        cmd = (command or "").strip().lower()
        if cmd == "new-note":
            self.handle_new_note_request()
        elif cmd == "show":
            self._show_main_window()

    def handle_new_note_request(self) -> None:
        """앱 외부에서 트리거된 경우 요청이 도달했음을 보이도록 메인 창을 먼저 띄운다."""
        self._show_main_window()
        self._create_note(self._settings.default_note_color)

    def _open_history(self) -> None:
        self._ensure_history_viewer()
        self._history_viewer.set_notes(list(self._notes.values()))
        self._history_viewer.show()
        self._history_viewer.raise_()
        self._client.get_history(None)

    def _ensure_history_viewer(self) -> HistoryViewer:
        if self._history_viewer is None:
            self._history_viewer = HistoryViewer(self)
            self._history_viewer.restoreRequested.connect(
                self._on_restore_requested)
        return self._history_viewer

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self._settings, role=self._role, parent=self)
        dlg.backupNowRequested.connect(self.backupRequested.emit)
        dlg.exec()
        self._apply_tray_visibility()

    def _open_sessions(self) -> None:
        if self._sessions_dialog is None:
            self._sessions_dialog = SessionsDialog(self)
        self._refresh_sessions_dialog()
        self._sessions_dialog.show()
        self._sessions_dialog.raise_()
        self._sessions_dialog.activateWindow()

    def _refresh_sessions_dialog(self) -> None:
        if self._sessions_dialog is None:
            return
        ls = self._local.state
        if self._role == "host":
            # 호스트도 게스트와 같은 '주소:포트' 포맷을 보도록 본 PC 의 LAN 주소를 쓴다.
            peer_address = f"{_local_lan_ip()}:{ls.last_host_port}"
        else:
            peer_address = f"{ls.last_host_ip}:{ls.last_host_port}"
        self._sessions_dialog.refresh(
            host=self._host_nickname,
            online=set(self._users),
            my_nickname=self._client.nickname(),
            my_role=self._role,
            records=ls.users,
            connected=self._connected,
            heartbeat_ms=self._heartbeat_ms,
            peer_address=peer_address,
        )

    def _on_connection_changed(self, connected: bool) -> None:
        self._connected = connected
        if connected:
            self._status.showMessage(i18n.t("main.status_connected"))
        else:
            self._status.showMessage(i18n.t("main.status_disconnected"))
        self._refresh_sessions_dialog()

    def _on_error(self, message: str) -> None:
        self._status.showMessage(i18n.t("main.status_error", message=message), 5000)

    def _on_welcomed(self, data: dict) -> None:
        self._users = list(data.get("users", []))
        self._host_nickname = data.get("host", "") or self._host_nickname
        self._heartbeat_ms = int(data.get("heartbeat_ms", 0)) or self._heartbeat_ms
        # welcome 마다 처음부터 재구성해 재연결도 깔끔하게 처리한다.
        self._folders = {
            f["id"]: f for f in (data.get("folders") or [])
        }
        if (self._current_folder not in (FOLDER_ALL, FOLDER_NONE)
                and self._current_folder not in self._folders):
            self._current_folder = FOLDER_ALL
        self._refresh_folder_chip()
        self._refresh_card_folder_context()
        # 아래에서 기존 메모를 닫기 전에 teardown 으로 표시한다. 그러지 않으면
        # closeEvent 의 hideRequested 가 local_state 를 hidden=True 로 바꿔, 재구성된
        # 메모가 전부 숨겨진 채 시작된다(짧은 단절 후 재접속이나 재시작 시 관측).
        for w in self._stickies.values():
            w._teardown = True
        # 접속 시점에 이미 명단에 있던 참가자의 세션 시작 시각은 알 수 없으므로
        # 본인만 지금으로 찍고 나머지는 0 으로 둔다(이후 join 은 user_joined 가 채운다).
        me = self._client.nickname()
        for nick in self._users:
            self._local.state.touch_user_in_session(nick, is_self=(nick == me))
        self._local.save()
        self._refresh_sessions_dialog()
        self._refresh_status_text()
        for w in list(self._stickies.values()):
            w.close()
            w.deleteLater()
        self._stickies.clear()
        for c in list(self._cards.values()):
            c.setParent(None)
            c.deleteLater()
        self._cards.clear()
        self._notes.clear()
        self._locks = dict(data.get("locks", {}))
        sorted_notes = sorted(
            data.get("notes", []),
            key=lambda n: n.get("updated_at", 0),
            reverse=True,
        )
        for note in sorted_notes:
            self._notes[note["id"]] = note
            self._append_card(note)
        self._apply_search_filter()
        for note in sorted_notes:
            self._ensure_sticky(note)

    def _on_note_created(self, note: dict) -> None:
        self._notes[note["id"]] = note
        self._append_card(note)
        self._move_card_to_top(note["id"])
        self._apply_search_filter()
        # 한 번의 "새 메모" 클릭이 협업자 모두의 바탕 화면에 창을 띄우지 않도록,
        # 만든 사용자에게만 띄우고 나머지 클라이언트에서는 숨김으로 둔다.
        is_creator = (note.get("created_by") == self._client.nickname())
        st = self._local.state.get_note_state(note["id"])
        st.hidden = not is_creator
        self._local.save()
        self._ensure_sticky(note)
        self._invalidate_tray_menu()

    def _on_note_updated(self, note: dict) -> None:
        self._notes[note["id"]] = note
        c = self._cards.get(note["id"])
        if c is not None:
            c.update_from(note, visible=not self._local.state.get_note_state(note["id"]).hidden)
        w = self._stickies.get(note["id"])
        if w is not None:
            w.apply_server_state(note)
        # 서버는 실제 변경에만 note_updated 를 보내므로, 도착할 때마다 맨 위로 올린다.
        self._move_card_to_top(note["id"])
        self._apply_search_filter()
        self._invalidate_tray_menu()

    def _move_card_to_top(self, note_id: str) -> None:
        card = self._cards.get(note_id)
        if card is None:
            return
        self._cards_layout.removeWidget(card)
        # 마지막 stretch 를 하단에 유지하려고 인덱스 0 에 삽입한다.
        self._cards_layout.insertWidget(0, card)

    def _on_note_deleted(self, note_id: str) -> None:
        self._notes.pop(note_id, None)
        if note_id in self._selected_notes:
            self._selected_notes.discard(note_id)
            self._refresh_bulk_bar()
        c = self._cards.pop(note_id, None)
        if c is not None:
            c.setParent(None)
            c.deleteLater()
        w = self._stickies.pop(note_id, None)
        if w is not None:
            # closeEvent 의 hideRequested 가 local_state 를 오염시키지 않도록
            # teardown 으로 표시한 뒤 닫는다(_on_welcomed 와 같은 예방책).
            w._teardown = True
            w.close()
            w.deleteLater()
        self._local.state.remove_note(note_id)
        self._local.save()
        self._apply_search_filter()
        self._invalidate_tray_menu()

    def _on_folder_created(self, folder: dict) -> None:
        if not folder.get("id"):
            return
        self._folders[folder["id"]] = folder
        self._refresh_folder_chip()
        self._refresh_card_folder_context()

    def _on_folder_updated(self, folder: dict) -> None:
        if not folder.get("id"):
            return
        self._folders[folder["id"]] = folder
        if self._current_folder == folder["id"]:
            self._refresh_folder_chip()
        self._refresh_card_folder_context()
        self._apply_search_filter()

    def _on_folder_deleted(self, folder_id: str) -> None:
        self._folders.pop(folder_id, None)
        if self._current_folder == folder_id:
            self._current_folder = FOLDER_ALL
        self._refresh_folder_chip()
        self._refresh_card_folder_context()
        self._apply_search_filter()

    def _refresh_card_folder_context(self) -> None:
        ctx = self._folder_context_for_cards()
        for card in self._cards.values():
            card.set_folder_context(ctx)

    def _refresh_folder_chip(self) -> None:
        label, _ = self._current_folder_label_and_color()
        self._folder_chip.setText(f"{label}    ▾")
        cf = self._current_folder
        is_private_folder = (
            cf not in (FOLDER_ALL, FOLDER_NONE)
            and bool((self._folders.get(cf) or {}).get("private_owner"))
        )
        icon_name = "lock" if is_private_folder else "folder"
        self._folder_chip.setIcon(svg_icon(icon_name, color="#3A3A3A"))

    def _current_folder_label_and_color(self) -> tuple[str, str]:
        cf = self._current_folder
        if cf == FOLDER_ALL:
            return i18n.t("main.folder_all"), "#7B7B7B"
        if cf == FOLDER_NONE:
            return i18n.t("main.folder_uncategorized"), "#7B7B7B"
        f = self._folders.get(cf)
        if not f:
            return i18n.t("main.folder_all"), "#7B7B7B"
        name = f.get("name") or i18n.t("main.folder_default_name")
        label = (i18n.t("main.folder_private_label", name=name)
                 if f.get("private_owner") else name)
        return label, f.get("color") or config.DEFAULT_COLOR

    def _show_folder_selector(self) -> None:
        menu = QMenu(self._folder_chip)
        add_centered_menu_action(
            menu, svg_icon("folder"), i18n.t("main.folder_all"),
            lambda: self._select_folder(FOLDER_ALL))
        add_centered_menu_action(
            menu, None, i18n.t("main.folder_uncategorized"),
            lambda: self._select_folder(FOLDER_NONE))
        folders = sorted(
            self._folders.values(),
            key=lambda f: (f.get("name") or "").lower(),
        )
        if folders:
            menu.addSeparator()
            for f in folders:
                name = f.get("name") or i18n.t("main.folder_default_name")
                if f.get("private_owner"):
                    name = i18n.t("main.folder_private_label", name=name)
                    icon = svg_icon("lock", color="#5B5B5B")
                else:
                    color = f.get("color") or config.DEFAULT_COLOR
                    icon = color_swatch_icon(color)
                fid = f["id"]
                add_centered_menu_action(
                    menu, icon, name,
                    lambda _fid=fid: self._select_folder(_fid))
        menu.addSeparator()
        add_centered_menu_action(
            menu, svg_icon("plus"), i18n.t("main.menu_new_folder"),
            self._create_folder_dialog)
        menu.exec(self._folder_chip.mapToGlobal(
            QPoint(0, self._folder_chip.height())))

    def _show_folder_menu(self) -> None:
        cf = self._current_folder
        is_real = cf not in (FOLDER_ALL, FOLDER_NONE)
        menu = QMenu(self._folder_menu_btn)
        add_centered_menu_action(
            menu, svg_icon("eye_on"), i18n.t("main.menu_folder_show_all"),
            lambda: self._bulk_set_folder_visibility(True))
        add_centered_menu_action(
            menu, svg_icon("eye_off"), i18n.t("main.menu_folder_hide_all"),
            lambda: self._bulk_set_folder_visibility(False))
        add_centered_menu_action(
            menu, svg_icon("clock"), i18n.t("main.menu_folder_history"),
            self._open_folder_history)
        if is_real:
            menu.addSeparator()
            add_centered_menu_action(
                menu, None, i18n.t("main.menu_folder_edit"),
                self._edit_current_folder)
            add_centered_menu_action(
                menu, None, i18n.t("main.menu_folder_delete"),
                self._delete_current_folder)
        menu.exec(self._folder_menu_btn.mapToGlobal(
            QPoint(0, self._folder_menu_btn.height())))

    def _select_folder(self, folder_id: str) -> None:
        self._current_folder = folder_id
        self._refresh_folder_chip()
        self._apply_search_filter()

    def _create_folder_dialog(self) -> None:
        dlg = FolderEditDialog(title=i18n.t("main.dialog_new_folder_title"), parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        name = dlg.name() or i18n.t("main.folder_new_default_name")
        self._client.create_folder(name, dlg.color(), dlg.private())

    def _edit_current_folder(self) -> None:
        f = self._folders.get(self._current_folder)
        if f is None:
            return
        dlg = FolderEditDialog(
            title=i18n.t("main.dialog_edit_folder_title"),
            name=f.get("name") or "",
            color=f.get("color") or config.DEFAULT_COLOR,
            private=bool(f.get("private_owner")),
            parent=self,
        )
        if dlg.exec() != QDialog.Accepted:
            return
        kwargs: dict = {}
        new_name = dlg.name() or (f.get("name") or "")
        if new_name != f.get("name"):
            kwargs["name"] = new_name
        if dlg.color() != f.get("color"):
            kwargs["color"] = dlg.color()
        if dlg.private() != bool(f.get("private_owner")):
            kwargs["private"] = dlg.private()
        if kwargs:
            self._client.update_folder(f["id"], **kwargs)

    def _delete_current_folder(self) -> None:
        f = self._folders.get(self._current_folder)
        if f is None:
            return
        reply = QMessageBox.question(
            self, i18n.t("main.msg_folder_delete_title"),
            i18n.t("main.msg_folder_delete_body", name=f.get('name', '')),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        self._client.delete_folder(f["id"])

    def _bulk_set_folder_visibility(self, visible: bool) -> None:
        for note_id, note in self._notes.items():
            if not self._note_in_current_folder(note):
                continue
            self._set_note_visibility(note_id, visible)

    def _open_folder_history(self) -> None:
        self._open_history()

    def _note_in_current_folder(self, note: dict) -> bool:
        cf = self._current_folder
        nfid = note.get("folder_id") or None
        if cf == FOLDER_ALL:
            return True
        if cf == FOLDER_NONE:
            return nfid is None
        return nfid == cf

    def _on_lock_granted(self, note_id: str) -> None:
        self._locks[note_id] = self._client.nickname()
        # 복원용으로 잡은 잠금이면 스냅샷만 푸시하고 곧바로 해제한다(편집 모드로 열지 않음).
        pending_content = self._pending_restore.pop(note_id, None)
        if pending_content is not None:
            note = self._notes.get(note_id)
            if note is None:
                self._client.release_lock(note_id)
                return
            self._client.update_note(
                note_id,
                pending_content,
                note.get("color", config.DEFAULT_COLOR),
                int(note.get("width", config.DEFAULT_NOTE_WIDTH)),
                int(note.get("height", config.DEFAULT_NOTE_HEIGHT)),
                int(note.get("version", 1)),
            )
            self._client.release_lock(note_id)
            self._status.showMessage(i18n.t("main.status_note_restored"), 4000)
            return
        w = self._stickies.get(note_id)
        if w is not None:
            w.enter_edit_mode()

    def _on_lock_denied(self, note_id: str, holder: str) -> None:
        # 복원 대기 중 거부면 조용히 넘기지 말고 복원 불가를 알린다.
        if self._pending_restore.pop(note_id, None) is not None:
            QMessageBox.information(
                self,
                i18n.t("main.msg_restore_unavailable_title"),
                i18n.t("main.msg_restore_locked_body",
                       holder=holder or i18n.t("main.other_user")),
            )
            return
        w = self._stickies.get(note_id)
        if w is not None:
            w.show_lock_denied(holder or i18n.t("main.other_user"))

    def _on_restore_requested(self, note_id: str, content: str) -> None:
        """표준 lock → update → release 흐름으로 처리해야 서버가 롤백에 대한
        새 이력 항목을 만들고 모든 클라이언트가 변경을 받아 본다."""
        if note_id not in self._notes:
            QMessageBox.warning(
                self, i18n.t("main.msg_restore_unavailable_title"),
                i18n.t("main.msg_restore_note_gone_body"))
            return
        self._pending_restore[note_id] = content
        self._client.acquire_lock(note_id)

    def _on_lock_held(self, note_id: str, holder: str) -> None:
        self._locks[note_id] = holder
        w = self._stickies.get(note_id)
        if w is not None:
            w.set_lock_holder(holder)

    def _on_lock_released(self, note_id: str) -> None:
        self._locks.pop(note_id, None)
        w = self._stickies.get(note_id)
        if w is not None:
            w.set_lock_holder(None)

    def _on_user_joined(self, nickname: str) -> None:
        if nickname not in self._users:
            self._users.append(nickname)
        self._local.state.touch_user(nickname, joined=True)
        self._local.save()
        self._refresh_status_text()
        self._refresh_sessions_dialog()
        self._status.showMessage(i18n.t("main.status_user_joined", nick=nickname), 3000)

    def _on_user_left(self, nickname: str) -> None:
        if nickname in self._users:
            self._users.remove(nickname)
        # 참가자 대화상자가 last_seen_at 이 아니라 last_disconnected_at 으로
        # 세션 종료 시각을 보여주므로, 여기서 disconnect 시점을 명시적으로 찍는다.
        self._local.state.touch_user(
            nickname, joined=False, disconnected=True)
        self._local.save()
        self._refresh_status_text()
        self._refresh_sessions_dialog()
        self._status.showMessage(i18n.t("main.status_user_left", nick=nickname), 3000)

    def _on_history_appended(self, entry: dict) -> None:
        if self._history_viewer is not None and self._history_viewer.isVisible():
            self._history_viewer.append_entry(entry)

    def _on_history_list(self, _note_id: str, entries: list) -> None:
        if self._history_viewer is not None:
            self._history_viewer.set_entries(entries)

    def _append_card(self, note: dict) -> None:
        if note["id"] in self._cards:
            self._cards[note["id"]].update_from(
                note,
                visible=not self._local.state.get_note_state(note["id"]).hidden,
            )
            self._cards[note["id"]].set_folder_context(
                self._folder_context_for_cards())
            return
        card = _NoteCard(
            note,
            visible=not self._local.state.get_note_state(note["id"]).hidden,
        )
        card.set_folder_context(self._folder_context_for_cards())
        if self._selection_mode:
            card.set_selection_mode(True)
        card.clicked.connect(self._on_card_clicked)
        card.rangeClickRequested.connect(self._on_card_range_click)
        card.toggleVisibility.connect(self._toggle_visibility_from_card)
        card.deleteRequested.connect(self._delete_note_confirm)
        card.historyRequested.connect(self._open_history_for)
        card.privateToggleRequested.connect(self._on_card_private_toggled)
        card.moveToFolderRequested.connect(self._on_card_move_to_folder)
        self._cards[note["id"]] = card
        self._cards_layout.insertWidget(self._cards_layout.count() - 1, card)

    def _folder_context_for_cards(self) -> list[tuple[str, str]]:
        return [
            (fid, (i18n.t("main.folder_private_label",
                          name=f.get("name") or i18n.t("main.folder_default_name"))
                   if f.get("private_owner")
                   else (f.get("name") or i18n.t("main.folder_default_name"))))
            for fid, f in sorted(
                self._folders.items(),
                key=lambda kv: (kv[1].get("name") or "").lower())
        ]

    def _on_select_mode_toggled(self, on: bool) -> None:
        self._selection_mode = on
        if not on:
            self._selected_notes.clear()
            self._selection_anchor = None
        for card in self._cards.values():
            card.set_selection_mode(on)
            card.set_selected(False)
        self._bulk_bar.setVisible(on)
        self._refresh_bulk_bar()
        if on:
            self._status.showMessage(
                i18n.t("main.status_selection_hint"),
                4000)

    def _refresh_bulk_bar(self) -> None:
        count = len(self._selected_notes)
        self._bulk_count_lbl.setText(i18n.t("main.bulk_selected_count", count=count))
        for btn in (self._bulk_folder_btn,
                    self._bulk_private_btn,
                    self._bulk_delete_btn):
            btn.setEnabled(count > 0)
        visible_ids = self._visible_card_ids()
        all_selected = (
            bool(visible_ids)
            and visible_ids.issubset(self._selected_notes))
        self._bulk_select_all_btn.setText(
            i18n.t("main.bulk_deselect_all") if all_selected
            else i18n.t("main.bulk_select_all"))

    def _visible_card_ids(self) -> set[str]:
        return {nid for nid, c in self._cards.items()
                if c.isVisible()}

    def _visible_card_ids_ordered(self) -> list[str]:
        """Shift+Click 범위가 사용자가 보는 순서와 일치하도록 화면 순서대로 반환한다."""
        visible = [(nid, c) for nid, c in self._cards.items()
                   if c.isVisible()]
        visible.sort(key=lambda x: self._cards_layout.indexOf(x[1]))
        return [nid for nid, _ in visible]

    def _on_card_range_click(self, note_id: str) -> None:
        """anchor 와 이번 클릭 사이의 가시 카드를 양 끝 포함으로 선택한다.
        anchor 가 없으면 단일 토글로 폴백한다."""
        if not self._selection_mode:
            return
        anchor = self._selection_anchor
        if anchor is None or anchor == note_id:
            self._on_card_clicked(note_id)
            return
        ordered = self._visible_card_ids_ordered()
        if anchor not in ordered or note_id not in ordered:
            self._on_card_clicked(note_id)
            return
        a_idx = ordered.index(anchor)
        n_idx = ordered.index(note_id)
        if a_idx > n_idx:
            a_idx, n_idx = n_idx, a_idx
        for rid in ordered[a_idx:n_idx + 1]:
            self._selected_notes.add(rid)
            card = self._cards.get(rid)
            if card is not None:
                card.set_selected(True)
        # 연속 Shift+Click 이 최근 끝점에서 계속 확장되도록 대상을 새 anchor 로 둔다.
        self._selection_anchor = note_id
        self._refresh_bulk_bar()

    def _select_all_via_shortcut(self) -> None:
        if not self._selection_mode:
            self._select_btn.setChecked(True)
        visible_ids = self._visible_card_ids()
        if not visible_ids:
            return
        self._selected_notes |= visible_ids
        for nid, card in self._cards.items():
            card.set_selected(nid in self._selected_notes)
        self._refresh_bulk_bar()

    def _bulk_select_all(self) -> None:
        visible_ids = self._visible_card_ids()
        all_selected = (
            bool(visible_ids)
            and visible_ids.issubset(self._selected_notes))
        if all_selected:
            self._selected_notes -= visible_ids
        else:
            self._selected_notes |= visible_ids
        for nid, card in self._cards.items():
            card.set_selected(nid in self._selected_notes)
        self._refresh_bulk_bar()

    def _bulk_show_folder_menu(self) -> None:
        if not self._selected_notes:
            return
        menu = QMenu(self._bulk_folder_btn)
        add_centered_menu_action(
            menu, None, i18n.t("main.folder_uncategorized"),
            lambda: self._bulk_apply_folder(None))
        if self._folders:
            menu.addSeparator()
            for fid, fname in self._folder_context_for_cards():
                add_centered_menu_action(
                    menu, None, fname,
                    lambda _fid=fid: self._bulk_apply_folder(_fid))
        menu.exec(self._bulk_folder_btn.mapToGlobal(
            QPoint(0, -menu.sizeHint().height())))

    def _bulk_apply_folder(self, folder_id) -> None:
        ids = list(self._selected_notes)
        for nid in ids:
            if nid not in self._notes:
                continue
            note = self._notes[nid]
            note["folder_id"] = folder_id
            card = self._cards.get(nid)
            if card is not None:
                card.update_from(
                    note,
                    visible=not self._local.state.get_note_state(nid).hidden,
                )
            self._client.set_note_folder(nid, folder_id)
        self._apply_search_filter()
        target = ((self._folders.get(folder_id, {}) or {}).get("name")
                  if folder_id else i18n.t("main.folder_uncategorized"))
        self._status.showMessage(
            i18n.t("main.bulk_moved", count=len(ids), folder=target),
            4000)
        self._exit_selection_mode()

    def _bulk_show_privacy_menu(self) -> None:
        menu = QMenu(self._bulk_private_btn)
        add_centered_menu_action(
            menu, svg_icon("lock", color="#3A3A3A"),
            i18n.t("main.menu_bulk_set_private"),
            lambda: self._bulk_apply_privacy(True))
        add_centered_menu_action(
            menu, None, i18n.t("main.menu_bulk_set_public"),
            lambda: self._bulk_apply_privacy(False))
        menu.exec(self._bulk_private_btn.mapToGlobal(
            QPoint(0, -menu.sizeHint().height())))

    def _bulk_apply_privacy(self, private: bool) -> None:
        ids = list(self._selected_notes)
        for nid in ids:
            if nid not in self._notes:
                continue
            note = self._notes[nid]
            note["private_owner"] = (
                self._client.nickname() if private else None)
            card = self._cards.get(nid)
            if card is not None:
                card.update_from(
                    note,
                    visible=not self._local.state.get_note_state(nid).hidden,
                )
            w = self._stickies.get(nid)
            if w is not None:
                w.apply_server_state(note)
            self._client.set_note_privacy(nid, private)
        self._status.showMessage(
            i18n.t("main.bulk_privacy_on", count=len(ids)) if private
            else i18n.t("main.bulk_privacy_off", count=len(ids)),
            4000)
        self._exit_selection_mode()

    def _bulk_delete(self) -> None:
        ids = list(self._selected_notes)
        if not ids:
            return
        reply = QMessageBox.question(
            self, i18n.t("main.msg_bulk_delete_title"),
            i18n.t("main.msg_bulk_delete_body", count=len(ids)),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        for nid in ids:
            if nid in self._notes:
                self._client.delete_note(nid)
        self._status.showMessage(
            i18n.t("main.bulk_deleted", count=len(ids)), 4000)
        self._exit_selection_mode()

    def _exit_selection_mode(self) -> None:
        if not self._selection_mode:
            return
        # _on_select_mode_toggled 가 두 번 재귀되지 않도록 토글 시그널을 막는다.
        self._select_btn.blockSignals(True)
        self._select_btn.setChecked(False)
        self._select_btn.blockSignals(False)
        self._on_select_mode_toggled(False)

    def _on_card_private_toggled(self, note_id: str, private: bool) -> None:
        """로컬 사본을 먼저 바꾸는 낙관적 갱신이라, MSG_SET_NOTE_PRIVACY 를
        무시하는 구버전 호스트와 통신해도 최소한 로컬 피드백은 보장된다."""
        note = self._notes.get(note_id)
        if note is not None:
            note["private_owner"] = (
                self._client.nickname() if private else None)
            c = self._cards.get(note_id)
            if c is not None:
                c.update_from(
                    note,
                    visible=not self._local.state.get_note_state(note_id).hidden,
                )
            w = self._stickies.get(note_id)
            if w is not None:
                w.apply_server_state(note)
        self._client.set_note_privacy(note_id, private)
        self._status.showMessage(
            i18n.t("main.status_note_private_on") if private
            else i18n.t("main.status_note_private_off"),
            4000)

    def _on_card_move_to_folder(self, note_id: str,
                                  folder_id) -> None:
        note = self._notes.get(note_id)
        if note is not None:
            note["folder_id"] = folder_id
            c = self._cards.get(note_id)
            if c is not None:
                c.update_from(
                    note,
                    visible=not self._local.state.get_note_state(note_id).hidden,
                )
        self._client.set_note_folder(note_id, folder_id)
        self._apply_search_filter()
        if folder_id is None:
            self._status.showMessage(i18n.t("main.status_note_moved_uncategorized"), 3000)
        else:
            fname = ((self._folders.get(folder_id, {}) or {}).get("name")
                     or i18n.t("main.folder_default_name"))
            self._status.showMessage(
                i18n.t("main.status_note_moved_folder", folder=fname), 3000)

    def _on_card_clicked(self, note_id: str) -> None:
        if self._selection_mode:
            if note_id in self._selected_notes:
                self._selected_notes.discard(note_id)
            else:
                self._selected_notes.add(note_id)
            card = self._cards.get(note_id)
            if card is not None:
                card.set_selected(note_id in self._selected_notes)
            # Shift+Click 이 범위 계산에 쓰도록 마지막 일반 클릭을 anchor 로 기록한다.
            self._selection_anchor = note_id
            self._refresh_bulk_bar()
            return
        st = self._local.state.get_note_state(note_id)
        if st.hidden:
            self._set_note_visibility(note_id, True)
        w = self._stickies.get(note_id)
        if w is not None:
            w.raise_()
            w.activateWindow()

    def _toggle_visibility_from_card(self, note_id: str) -> None:
        st = self._local.state.get_note_state(note_id)
        # 현재 hidden 값을 새 visible 로 넘겨 가시 상태를 뒤집는다.
        self._set_note_visibility(note_id, st.hidden)

    def _delete_note_confirm(self, note_id: str) -> None:
        reply = QMessageBox.question(
            self, i18n.t("main.msg_delete_confirm_title"),
            i18n.t("main.msg_delete_confirm_body"))
        if reply == QMessageBox.Yes:
            self._client.delete_note(note_id)

    def _refresh_empty_hint(self) -> None:
        total = len(self._notes)
        if not total:
            self._empty_hint.setText(i18n.t("main.hint_no_notes"))
            return
        visible = sum(1 for c in self._cards.values() if c.isVisible())
        # "7 / 7개" 같은 잡음을 피하려고 일부가 가려진 경우에만 분수로 표시한다.
        if visible == total:
            self._empty_hint.setText(i18n.t("main.hint_count_total", total=total))
        else:
            self._empty_hint.setText(
                i18n.t("main.hint_count_partial", visible=visible, total=total))

    def _apply_search_filter(self, text: str | None = None) -> None:
        """폴더 선택과 검색어를 AND 로 결합해 카드 가시성을 정한다."""
        if text is None:
            text = self._search_input.text()
        query = (text or "").strip().lower()
        self._search_query = query
        for note_id, card in self._cards.items():
            note = self._notes.get(note_id, {})
            in_folder = self._note_in_current_folder(note)
            if not in_folder:
                card.setVisible(False)
                continue
            if not query:
                card.setVisible(True)
                continue
            plain = html_to_plain(note.get("content") or "").lower()
            card.setVisible(query in plain)
        self._refresh_empty_hint()

    def _ensure_sticky(self, note: dict) -> None:
        note_id = note["id"]
        if note_id in self._stickies:
            w = self._stickies[note_id]
            w.apply_server_state(note)
        else:
            w = StickyNoteWidget(
                note, self._client.nickname(),
                default_font_size=self._settings.default_font_size,
                settings=self._settings,
            )
            w.requestLock.connect(self._client.acquire_lock)
            w.releaseLock.connect(self._client.release_lock)
            w.commitEdit.connect(self._on_commit_edit)
            w.deleteRequested.connect(self._delete_note_confirm)
            w.hideRequested.connect(
                lambda nid: self._set_note_visibility(nid, False))
            w.historyRequested.connect(self._open_history_for)
            w.privateToggleRequested.connect(
                self._on_card_private_toggled)
            w.positionChanged.connect(self._on_position_changed)
            w.sizeChanged.connect(self._on_size_changed)
            self._stickies[note_id] = w

        st = self._local.state.get_note_state(note_id)
        w.move(st.x, st.y)
        # 창 크기는 위치처럼 클라이언트별 로컬 상태다. 저장된 값이 있으면
        # 서버 기본 크기보다 우선한다.
        if st.w and st.h:
            w.resize(st.w, st.h)
        holder = self._locks.get(note_id)
        if holder and holder != self._client.nickname():
            w.set_lock_holder(holder)
        else:
            w.set_lock_holder(None)
        if not st.hidden:
            w.show()
        else:
            w.hide()

    def _on_commit_edit(self, note_id: str, content: str, color: str,
                        w: int, h: int, version: int) -> None:
        self._client.update_note(note_id, content, color, w, h, version)

    def _on_position_changed(self, note_id: str, x: int, y: int) -> None:
        self._local.state.set_note_state(note_id, x=x, y=y)
        self._local.save()

    def _on_size_changed(self, note_id: str, w: int, h: int) -> None:
        self._local.state.set_note_state(note_id, w=w, h=h)
        self._local.save()

    def _set_note_visibility(self, note_id: str, visible: bool) -> None:
        self._local.state.set_note_state(note_id, hidden=not visible)
        self._local.save()
        w = self._stickies.get(note_id)
        if w is not None:
            if visible:
                w.show()
                w.raise_()
            else:
                w.hide()
        card = self._cards.get(note_id)
        if card is not None:
            card.set_visible(visible)

    def _open_history_for(self, note_id: str) -> None:
        self._ensure_history_viewer()
        self._history_viewer.set_notes(list(self._notes.values()))
        idx = self._history_viewer._note_combo.findData(note_id)
        if idx >= 0:
            self._history_viewer._note_combo.setCurrentIndex(idx)
        self._history_viewer.show()
        self._history_viewer.raise_()
        self._client.get_history(None)

    def _refresh_status_text(self) -> None:
        label = f"{self._role} · {self._client.nickname()}"
        if self._users:
            label += "   " + i18n.t("main.status_online_count", count=len(self._users))
        self._status.showMessage(label)

    def _build_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        icon = self._app_icon or self.windowIcon()
        self._tray = QSystemTrayIcon(icon, self)
        self._tray.setToolTip(config.APP_NAME)
        menu = QMenu()
        menu.aboutToShow.connect(self._rebuild_tray_menu)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray_menu_dirty = True
        self._apply_tray_visibility()

    def _apply_tray_visibility(self) -> None:
        if self._tray is None:
            return
        if self._settings.show_tray_icon:
            self._tray.show()
        else:
            self._tray.hide()

    def _invalidate_tray_menu(self) -> None:
        self._tray_menu_dirty = True

    def _add_tray_item(
        self, menu: QMenu, icon: QIcon | None, text: str,
        handler=None, enabled: bool = True,
    ) -> None:
        add_centered_menu_action(menu, icon, text, handler, enabled=enabled)

    def _rebuild_tray_menu(self) -> None:
        if self._tray is None:
            return
        menu = self._tray.contextMenu()
        menu.clear()

        self._add_tray_item(
            menu, svg_icon("plus"), i18n.t("main.btn_new_note"),
            lambda: self._create_note(self._settings.default_note_color))
        menu.addSeparator()

        items = sorted(
            self._notes.values(),
            key=lambda n: n.get("updated_at", 0),
            reverse=True,
        )[:15]
        if items:
            self._add_tray_item(menu, None, i18n.t("main.tray_notes_list"), enabled=False)
            for note in items:
                raw = note.get("content") or ""
                plain = html_to_plain(raw)
                first_line = (plain.splitlines() or [""])[0]
                if first_line:
                    title = first_line
                elif has_non_checkbox_image(raw):
                    title = i18n.t("main.note_title_image")
                else:
                    title = i18n.t("main.note_title_empty")
                if len(title) > 40:
                    title = title[:40] + "…"
                nid = note["id"]
                self._add_tray_item(
                    menu, None, title,
                    lambda _id=nid: self._show_from_tray(_id))
        else:
            self._add_tray_item(menu, None, i18n.t("main.tray_no_notes"), enabled=False)

        menu.addSeparator()
        self._add_tray_item(menu, None, i18n.t("main.tray_show_main"),
                             self._show_main_window)
        self._add_tray_item(menu, svg_icon("users"), i18n.t("main.tray_sessions"),
                             self._open_sessions)
        self._add_tray_item(menu, svg_icon("settings"), i18n.t("main.tray_settings"),
                             self._open_settings)
        self._add_tray_item(menu, None, i18n.t("main.tray_change_connection"),
                             self._reset_connection)

        menu.addSeparator()
        self._add_tray_item(menu, None, i18n.t("main.tray_quit"), self._quit_app)

        self._tray_menu_dirty = False

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            self._show_main_window()

    def _show_main_window(self) -> None:
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()

    def _show_from_tray(self, note_id: str) -> None:
        self._set_note_visibility(note_id, True)
        w = self._stickies.get(note_id)
        if w is not None:
            w.raise_()
            w.activateWindow()

    def _flush_pending_edits(self) -> None:
        """teardown 전에 호출해, 편집 중이던 내용이 재시작 시 사라지지 않게 한다."""
        for sticky in list(self._stickies.values()):
            try:
                sticky.flush_pending_edit()
            except Exception:
                pass

    def _teardown_stickies(self) -> None:
        """일반 close 흐름을 거치면 local_state 에 hidden 으로 표시돼 다음
        실행 시 사라지므로, 종료 시에는 teardown 으로 파괴한다."""
        for w in list(self._stickies.values()):
            w._teardown = True
            w.close()
            w.deleteLater()
        self._stickies.clear()

    def _reset_connection(self) -> None:
        """다음 실행 때 접속 대화상자가 다시 뜨도록 last_mode 만 지운다.
        앱을 종료하거나 현재 세션을 끊지는 않는다."""
        self._local.state.last_mode = ""
        self._local.save()
        mbox = QMessageBox(self)
        mbox.setIcon(QMessageBox.Information)
        mbox.setWindowTitle(i18n.t("main.msg_reset_connection_title"))
        mbox.setText(i18n.t("main.msg_reset_connection_body"))
        mbox.setStandardButtons(QMessageBox.Ok)
        ok_btn = mbox.button(QMessageBox.Ok)
        if ok_btn is not None:
            ok_btn.setText(i18n.t("main.btn_ok"))
            ok_btn.setMinimumWidth(96)
        bbox = mbox.findChild(QDialogButtonBox)
        if bbox is not None:
            bbox.setCenterButtons(True)
        mbox.exec()

    def _quit_app(self) -> None:
        self._force_quit = True
        self._flush_pending_edits()
        self._teardown_stickies()
        if self._tray is not None:
            self._tray.hide()
        self._client.stop()
        QApplication.quit()

    def closeEvent(self, event) -> None:
        # 트레이가 켜져 있으면 X 로 닫아도 숨기기만 해서 동기화를 유지한다.
        if (not self._force_quit
                and self._tray is not None
                and self._tray.isVisible()
                and self._settings.close_main_to_tray):
            event.ignore()
            self.hide()
            return
        self._flush_pending_edits()
        self._teardown_stickies()
        self._client.stop()
        if self._tray is not None:
            self._tray.hide()
        super().closeEvent(event)


def _soft_breakable(text: str, run_limit: int = 12) -> str:
    """공백 없는 긴 글자열(예: 무공백 CJK)도 카드 폭에서 줄바꿈되도록,
    연속 비공백이 일정 길이를 넘으면 제로폭 공백을 끼워 끊을 곳을 만든다."""
    out: list[str] = []
    run = 0
    for ch in text:
        out.append(ch)
        if ch.isspace():
            run = 0
        else:
            run += 1
            if run >= run_limit:
                out.append("​")
                run = 0
    return "".join(out)


class _NoteCard(QFrame):
    clicked = Signal(str)
    rangeClickRequested = Signal(str)
    toggleVisibility = Signal(str)
    deleteRequested = Signal(str)
    historyRequested = Signal(str)
    privateToggleRequested = Signal(str, bool)   # note_id, new_private
    moveToFolderRequested = Signal(str, object)  # note_id, folder_id|None

    _CARD_RADIUS = 12

    def __init__(self, note: dict, visible: bool, parent: QWidget | None = None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(92)

        self._note_id: str = note["id"]
        self._color: str = note.get("color", config.DEFAULT_COLOR)
        self._visible = visible
        self._updated_at: int = int(note.get("updated_at", 0))
        self._private: bool = bool(note.get("private_owner"))
        self._folder_context: list[tuple[str, str]] = []  # (id, name)
        self._selection_mode: bool = False
        self._selected: bool = False

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 14, 14)
        root.setSpacing(6)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(4)

        self._eye_btn = QToolButton()
        self._eye_btn.setIconSize(QSize(16, 16))
        self._eye_btn.setProperty("iconOnly", True)
        self._eye_btn.setCursor(Qt.PointingHandCursor)
        self._eye_btn.setToolTip(i18n.t("main.tooltip_toggle_desktop"))
        self._eye_btn.setFocusPolicy(Qt.NoFocus)
        self._eye_btn.clicked.connect(
            lambda: self.toggleVisibility.emit(self._note_id))

        self._image_indicator = QLabel()
        self._image_indicator.setFixedSize(20, 20)
        self._image_indicator.setAlignment(Qt.AlignCenter)
        self._image_indicator.setPixmap(
            svg_icon("image", color="#5B5B5B").pixmap(14, 14))
        self._image_indicator.setToolTip(i18n.t("main.tooltip_image_note"))
        self._image_indicator.setStyleSheet("background: transparent;")
        self._image_indicator.hide()

        # 시스템 emoji 폰트 영향을 받지 않도록 SVG 자물쇠로 배지를 만든다.
        self._private_indicator = QLabel()
        self._private_indicator.setFixedSize(22, 20)
        self._private_indicator.setAlignment(Qt.AlignCenter)
        self._private_indicator.setPixmap(
            svg_icon("lock", color="#1F2937").pixmap(14, 14))
        self._private_indicator.setToolTip(
            i18n.t("main.tooltip_private_note"))
        self._private_indicator.setStyleSheet(
            "background: rgba(0, 0, 0, 0.08); border-radius: 6px;")
        self._private_indicator.hide()

        self._menu_btn = QToolButton()
        self._menu_btn.setIconSize(QSize(16, 16))
        self._menu_btn.setIcon(svg_icon("more", color="#5B5B5B"))
        self._menu_btn.setProperty("iconOnly", True)
        self._menu_btn.setCursor(Qt.PointingHandCursor)
        self._menu_btn.setFocusPolicy(Qt.NoFocus)
        self._menu_btn.setToolTip(i18n.t("main.tooltip_menu"))
        self._menu_btn.clicked.connect(self._open_menu)

        self._timestamp = QLabel("")
        self._timestamp.setStyleSheet(
            "color: rgba(0, 0, 0, 0.55); font-size: 11px; background: transparent;")

        top.addWidget(self._eye_btn)
        top.addWidget(self._image_indicator)
        top.addWidget(self._private_indicator)
        top.addStretch(1)
        top.addWidget(self._timestamp)
        top.addWidget(self._menu_btn)
        root.addLayout(top)

        self._title = QLabel()
        self._title.setWordWrap(True)
        self._title.setStyleSheet(
            "font-size: 14px; font-weight: 700; color: #1F1F1F; background: transparent;")
        root.addWidget(self._title)

        self._body = QLabel()
        self._body.setWordWrap(True)
        self._body.setStyleSheet(
            "font-size: 12px; color: rgba(0, 0, 0, 0.66); background: transparent;")
        root.addWidget(self._body)
        root.addStretch(1)

        self.update_from(note, visible)

    def update_from(self, note: dict, visible: bool) -> None:
        self._note_id = note["id"]
        self._color = note.get("color", config.DEFAULT_COLOR)
        self._visible = visible
        self._updated_at = int(note.get("updated_at", 0))

        raw = note.get("content") or ""
        content = html_to_plain(raw)
        lines = [ln for ln in content.splitlines() if ln.strip()] or content.splitlines()
        # 체크박스 마커도 <img> 이므로 진짜 이미지 첨부만 가려낸다.
        has_image = has_non_checkbox_image(raw)
        has_text = bool(content.strip())
        image_only = has_image and not has_text

        if lines:
            title = lines[0]
            body = " ".join(lines[1:4])
        elif image_only:
            title = i18n.t("main.note_title_image")
            body = ""
        else:
            title = i18n.t("main.note_title_empty")
            body = ""

        if len(title) > 80:
            title = title[:80] + "…"
        if len(body) > 180:
            body = body[:180] + "…"

        self._title.setText(_soft_breakable(title))
        if body:
            self._body.setText(_soft_breakable(body))
            self._body.show()
        else:
            self._body.hide()

        self._image_indicator.setVisible(has_image)
        # 서버가 청중을 이미 필터링하므로, 이 메모가 도달했다면 본인이 곧 소유자다.
        self._private = bool(note.get("private_owner"))
        self._private_indicator.setVisible(self._private)

        self._timestamp.setText(_format_timestamp(self._updated_at))
        self._refresh_eye_icon()
        self.update()

    def set_visible(self, visible: bool) -> None:
        self._visible = visible
        self._refresh_eye_icon()

    def _refresh_eye_icon(self) -> None:
        name = "eye_on" if self._visible else "eye_off"
        self._eye_btn.setIcon(svg_icon(name, color="#5B5B5B"))

    def set_folder_context(self, folders: list[tuple[str, str]]) -> None:
        self._folder_context = list(folders)

    def set_selection_mode(self, on: bool) -> None:
        # 일괄 편집 중 카드별 동작이 실행되지 않도록 눈/메뉴 버튼을 비활성화한다.
        if self._selection_mode == on:
            return
        self._selection_mode = on
        if not on:
            self._selected = False
        self._eye_btn.setEnabled(not on)
        self._menu_btn.setEnabled(not on)
        self.update()

    def set_selected(self, selected: bool) -> None:
        if self._selected == selected:
            return
        self._selected = selected
        self.update()

    def is_selected(self) -> bool:
        return self._selected

    def _open_menu(self) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(_LIGHT_MENU_QSS)
        act_hist = menu.addAction(i18n.t("main.menu_edit_history"))
        act_hist.triggered.connect(
            lambda: self.historyRequested.emit(self._note_id))
        move_menu = menu.addMenu(i18n.t("main.menu_move_to_folder"))
        move_menu.setStyleSheet(_LIGHT_MENU_QSS)
        act_to_none = move_menu.addAction(i18n.t("main.folder_uncategorized"))
        act_to_none.triggered.connect(
            lambda: self.moveToFolderRequested.emit(self._note_id, None))
        if self._folder_context:
            move_menu.addSeparator()
            for fid, fname in self._folder_context:
                act = move_menu.addAction(fname)
                act.triggered.connect(
                    lambda _checked=False, _fid=fid:
                        self.moveToFolderRequested.emit(self._note_id, _fid))
        act_priv = menu.addAction(
            i18n.t("main.menu_private_off") if self._private
            else i18n.t("main.menu_private_on"))
        act_priv.triggered.connect(
            lambda: self.privateToggleRequested.emit(
                self._note_id, not self._private))
        menu.addSeparator()
        act_del = menu.addAction(i18n.t("main.menu_delete"))
        act_del.triggered.connect(
            lambda: self.deleteRequested.emit(self._note_id))
        menu.exec(self._menu_btn.mapToGlobal(
            QPoint(0, self._menu_btn.height())))

    def mousePressEvent(self, ev: QMouseEvent) -> None:
        if ev.button() == Qt.LeftButton:
            self._press_pos = ev.pos()
        super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev: QMouseEvent) -> None:
        if ev.button() == Qt.LeftButton and hasattr(self, "_press_pos"):
            if (ev.pos() - self._press_pos).manhattanLength() < 5:
                # 눈/메뉴 미니 버튼 위 클릭은 카드 클릭으로 처리하지 않는다.
                child = self.childAt(ev.pos())
                if child not in (self._eye_btn, self._menu_btn):
                    if (self._selection_mode
                            and ev.modifiers() & Qt.ShiftModifier):
                        self.rangeClickRequested.emit(self._note_id)
                    else:
                        self.clicked.emit(self._note_id)
        super().mouseReleaseEvent(ev)

    def contextMenuEvent(self, ev) -> None:
        self._open_menu()

    def paintEvent(self, ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(0, 0, -1, -1)
        p.setPen(QPen(QColor(0, 0, 0, 25), 1))
        p.setBrush(QColor(self._color))
        p.drawRoundedRect(rect, self._CARD_RADIUS, self._CARD_RADIUS)
        # 둥근 모서리가 깔끔하게 보이도록 선택 테두리는 약간 inset 으로 그린다.
        if self._selected:
            p.setPen(QPen(QColor("#3B82F6"), 2.5))
            p.setBrush(Qt.NoBrush)
            inset = rect.adjusted(1, 1, -1, -1)
            p.drawRoundedRect(inset,
                              self._CARD_RADIUS - 1,
                              self._CARD_RADIUS - 1)
        p.end()


def _format_timestamp(ms: int) -> str:
    return datetime_fmt.fmt_card_timestamp(ms)
