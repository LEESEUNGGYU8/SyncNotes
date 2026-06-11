from __future__ import annotations

from typing import Mapping

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .. import datetime_fmt, i18n
from ..local_state import UserRecord
from .theme import RoundedScrollBar


def _fmt_heartbeat(ms: int) -> str:
    return datetime_fmt.fmt_heartbeat(ms)


def _avatar_color(nick: str, *, online: bool) -> QColor:
    if not online:
        return QColor("#B5B5B5")
    seed = sum(ord(c) for c in nick) if nick else 0
    hue = (seed * 53 + 23) % 360
    return QColor.fromHsv(hue, 130, 195)


def _avatar_pixmap(nick: str, *, online: bool, size: int = 36) -> QPixmap:
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(_avatar_color(nick, online=online))
    p.drawEllipse(0, 0, size, size)
    letter = (nick[0] if nick else "?").upper()
    f = p.font()
    f.setBold(True)
    f.setPointSizeF(size * 0.42)
    p.setFont(f)
    p.setPen(QColor("#FFFFFF"))
    p.drawText(0, 0, size, size, Qt.AlignCenter, letter)
    p.end()
    return pix


class _Chip(QLabel):
    def __init__(self, text: str, *, fg: str, bg: str, parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setStyleSheet(
            f"background:{bg}; color:{fg}; "
            "border-radius: 7px; padding: 2px 8px; "
            "font-size: 10.5px; font-weight: 700;"
        )


class _SectionLabel(QWidget):
    def __init__(self, title: str, count: int, parent: QWidget | None = None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(2, 8, 2, 4)
        row.setSpacing(8)
        lbl = QLabel(title)
        lbl.setStyleSheet(
            "font-size: 12px; font-weight: 700; color: #6B6B6B; "
            "letter-spacing: 0.4px; text-transform: uppercase;")
        row.addWidget(lbl)
        chip = QLabel(str(count))
        chip.setStyleSheet(
            "background:#EEEEEE; color:#5B5B5B; "
            "border-radius: 9px; padding: 1px 8px; "
            "font-size: 10.5px; font-weight: 700;")
        row.addWidget(chip)
        row.addStretch(1)


class _UserCard(QFrame):
    def __init__(
        self,
        nickname: str,
        *,
        is_host: bool,
        is_self: bool,
        online: bool,
        status_text: str,
        sub_text: str,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("ParticipantCard")
        # 본인 행에만 틴트를 적용한다. 호스트는 행 배경 대신 이름 줄의 칩으로만
        # 표시해, 강조된 행이 두 개가 되지 않도록 한다.
        tint = "#EFF6FF" if is_self else "#FFFFFF"
        self.setStyleSheet(
            "QFrame#ParticipantCard {"
            f"  background: {tint};"
            "  border: 1px solid #ECECEC;"
            "  border-radius: 10px;"
            "}"
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 10, 14, 10)
        row.setSpacing(12)

        avatar = QLabel()
        avatar.setFixedSize(36, 36)
        avatar.setPixmap(_avatar_pixmap(nickname, online=online))
        row.addWidget(avatar, 0, Qt.AlignTop)

        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(2)

        name_row = QHBoxLayout()
        name_row.setContentsMargins(0, 0, 0, 0)
        name_row.setSpacing(6)
        name_lbl = QLabel(nickname)
        name_lbl.setStyleSheet(
            "font-size: 13.5px; font-weight: 700; color: #1F1F1F;")
        name_row.addWidget(name_lbl)
        if is_host:
            name_row.addWidget(_Chip(i18n.t("sessions.chip_host"), fg="#FFFFFF", bg="#1F2937"))
        else:
            name_row.addWidget(_Chip(i18n.t("sessions.chip_guest"), fg="#374151", bg="#E5E7EB"))
        if is_self:
            name_row.addWidget(_Chip(i18n.t("sessions.chip_self"), fg="#1D4ED8", bg="#DBEAFE"))
        name_row.addStretch(1)
        col.addLayout(name_row)

        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.setSpacing(6)
        dot = _Dot(online=online)
        status_row.addWidget(dot, 0, Qt.AlignVCenter)
        status_lbl = QLabel(status_text)
        status_lbl.setStyleSheet(
            "color: #1F8A4C; font-size: 11.5px; font-weight: 600;"
            if online else
            "color: #6B6B6B; font-size: 11.5px; font-weight: 600;"
        )
        status_row.addWidget(status_lbl)
        if sub_text:
            sep = QLabel("·")
            sep.setStyleSheet("color: #C0C0C0; font-size: 11.5px;")
            status_row.addWidget(sep)
            sub_lbl = QLabel(sub_text)
            sub_lbl.setStyleSheet("color: #6B6B6B; font-size: 11.5px;")
            status_row.addWidget(sub_lbl)
        status_row.addStretch(1)
        col.addLayout(status_row)

        row.addLayout(col, 1)


class _Dot(QLabel):
    def __init__(self, *, online: bool, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedSize(10, 10)
        pix = QPixmap(10, 10)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#22C55E" if online else "#B5B5B5"))
        p.drawEllipse(1, 1, 8, 8)
        p.end()
        self.setPixmap(pix)


def _kv_tile(key: str) -> tuple[QWidget, QLabel]:
    w = QWidget()
    col = QVBoxLayout(w)
    col.setContentsMargins(0, 0, 0, 0)
    col.setSpacing(2)
    k = QLabel(key)
    k.setStyleSheet(
        "color: #6B7280; font-size: 10.5px; font-weight: 700; "
        "letter-spacing: 0.3px;")
    col.addWidget(k)
    v = QLabel("")
    v.setStyleSheet(
        "color: #1F2937; font-size: 13px; font-weight: 700;")
    v.setWordWrap(True)
    v.setTextInteractionFlags(Qt.TextSelectableByMouse)
    col.addWidget(v)
    return w, v


class _SessionHeader(QFrame):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("SessionHeader")
        self.setStyleSheet(
            "QFrame#SessionHeader {"
            "  background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            "    stop:0 #FFFCF0, stop:1 #F3F8FF);"
            "  border: 1px solid #ECECEC;"
            "  border-radius: 12px;"
            "}"
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(10)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)

        self._host_name = QLabel("")
        self._host_name.setStyleSheet(
            "color: #1F1F1F; font-size: 17px; font-weight: 800;")
        self._host_name.setTextInteractionFlags(Qt.TextSelectableByMouse)
        top.addWidget(self._host_name, 0, Qt.AlignVCenter)

        self._host_badge = QLabel(i18n.t("sessions.chip_host"))
        self._host_badge.setStyleSheet(
            "background: #1F2937; color: #FFFFFF; "
            "border-radius: 7px; padding: 2px 8px; "
            "font-size: 10.5px; font-weight: 800; letter-spacing: 0.4px;")
        top.addWidget(self._host_badge, 0, Qt.AlignVCenter)
        top.addStretch(1)

        self._count_pill = QLabel("")
        self._count_pill.setStyleSheet(
            "background: rgba(31, 41, 55, 0.08); color: #1F2937; "
            "border-radius: 10px; padding: 4px 12px; "
            "font-size: 12px; font-weight: 700;")
        top.addWidget(self._count_pill, 0, Qt.AlignVCenter)
        outer.addLayout(top)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(
            "color: rgba(0, 0, 0, 0.08); "
            "background: rgba(0, 0, 0, 0.08); "
            "max-height: 1px; border: none;")
        outer.addWidget(sep)

        kv_grid = QGridLayout()
        kv_grid.setContentsMargins(0, 0, 0, 0)
        kv_grid.setHorizontalSpacing(18)
        kv_grid.setVerticalSpacing(10)
        name_tile, self._name_value = _kv_tile(i18n.t("sessions.kv_nickname"))
        role_tile, self._role_value = _kv_tile(i18n.t("sessions.kv_role"))
        addr_tile, self._addr_value = _kv_tile(i18n.t("sessions.kv_connection"))
        hb_tile, self._heartbeat_value = _kv_tile(i18n.t("sessions.kv_heartbeat"))
        kv_grid.addWidget(name_tile, 0, 0)
        kv_grid.addWidget(role_tile, 0, 1)
        kv_grid.addWidget(addr_tile, 1, 0)
        kv_grid.addWidget(hb_tile, 1, 1)
        kv_grid.setColumnStretch(0, 1)
        kv_grid.setColumnStretch(1, 1)
        outer.addLayout(kv_grid)

    def update_text(
        self,
        *,
        host: str,
        online_count: int,
        total_count: int,
        my_role: str,
        my_nickname: str,
        peer_address: str,
        heartbeat_ms: int,
        connected: bool,
    ) -> None:
        self._host_name.setText(host or i18n.t("sessions.host_unknown"))
        # 호스트를 아직 모를 때는 배지를 숨긴다. 플레이스홀더 이름 옆의 배지는
        # 의미 없는 장식이 되기 때문이다.
        self._host_badge.setVisible(bool(host))
        self._count_pill.setText(i18n.t(
            "sessions.count_pill", online=online_count, total=total_count))

        self._name_value.setText(my_nickname or i18n.t("sessions.nickname_unknown"))

        self._role_value.setText(
            i18n.t("sessions.chip_host") if my_role == "host"
            else i18n.t("sessions.chip_guest"))

        self._addr_value.setText(peer_address or i18n.t("sessions.address_unknown"))

        self._heartbeat_value.setText(_fmt_heartbeat(heartbeat_ms))


class SessionsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(i18n.t("sessions.window_title"))
        self.resize(480, 560)
        self.setMinimumSize(420, 380)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        self._header = _SessionHeader()
        root.addWidget(self._header)

        # 뷰포트를 transparent 로 둬야 QScrollArea 의 둥근 배경이 드러난다.
        # 기본값으로 두면 뷰포트의 Base 팔레트 색이 사각형으로 모서리를 덮는다.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setVerticalScrollBar(RoundedScrollBar())
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { background: #F8F9FB; "
            "border: 1px solid #ECECEC; border-radius: 12px; }"
        )
        scroll.viewport().setStyleSheet("background: transparent;")
        scroll.viewport().setAutoFillBackground(False)

        self._content = QWidget()
        self._content.setStyleSheet("background: transparent;")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(10, 10, 10, 10)
        self._content_layout.setSpacing(6)
        self._content_layout.addStretch(1)
        scroll.setWidget(self._content)
        root.addWidget(scroll, 1)

        self._empty = QLabel(i18n.t("sessions.empty_hint"))
        self._empty.setAlignment(Qt.AlignCenter)
        self._empty.setStyleSheet(
            "color:#A0A0A0; font-size: 12px; padding: 18px;")
        self._empty.hide()
        root.addWidget(self._empty)

        buttons = QDialogButtonBox(QDialogButtonBox.Close, parent=self)
        close_btn = buttons.button(QDialogButtonBox.Close)
        close_btn.setText(i18n.t("sessions.btn_close"))
        close_btn.setMinimumWidth(96)
        close_btn.setCursor(Qt.PointingHandCursor)
        buttons.rejected.connect(self.reject)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        bottom.addWidget(buttons)
        root.addLayout(bottom)

    def refresh(
        self,
        *,
        host: str,
        online: set[str],
        my_nickname: str,
        my_role: str,
        records: Mapping[str, UserRecord],
        connected: bool,
        heartbeat_ms: int = 0,
        peer_address: str = "",
    ) -> None:
        all_nicks: set[str] = set(online) | set(records.keys())
        if host:
            all_nicks.add(host)
        if my_nickname:
            all_nicks.add(my_nickname)

        online_nicks = [n for n in all_nicks if n in online]
        offline_nicks = [n for n in all_nicks if n not in online]

        # 온라인 정렬: 본인을 맨 위, 그다음 호스트(세션의 앵커), 나머지는
        # 알파벳 순으로 둔다.
        def online_sort_key(nick: str):
            return (
                0 if nick == my_nickname else 1,
                0 if nick == host else 1,
                nick.lower(),
            )

        # 오프라인: 최근에 본 사람 우선.
        def offline_sort_key(nick: str):
            rec = records.get(nick)
            seen = rec.last_seen_at if rec is not None else 0
            return (-seen, nick.lower())

        online_nicks.sort(key=online_sort_key)
        offline_nicks.sort(key=offline_sort_key)

        self._header.update_text(
            host=host,
            online_count=len(online_nicks),
            total_count=len(all_nicks),
            my_role=my_role,
            my_nickname=my_nickname,
            peer_address=peer_address,
            heartbeat_ms=heartbeat_ms,
            connected=connected,
        )

        self._clear_content()
        if not all_nicks:
            self._empty.show()
            self._content.hide()
            return
        self._empty.hide()
        self._content.show()

        if online_nicks:
            self._add_section(i18n.t("sessions.section_online"), len(online_nicks))
            for nick in online_nicks:
                rec = records.get(nick) or UserRecord()
                self._add_user_card(
                    nick,
                    online=True,
                    is_host=(nick == host),
                    is_self=(nick == my_nickname),
                    rec=rec,
                )

        if offline_nicks:
            self._add_section(i18n.t("sessions.section_offline"), len(offline_nicks))
            for nick in offline_nicks:
                rec = records.get(nick) or UserRecord()
                self._add_user_card(
                    nick,
                    online=False,
                    is_host=(nick == host),
                    is_self=(nick == my_nickname),
                    rec=rec,
                )

    def _clear_content(self) -> None:
        while self._content_layout.count() > 1:
            item = self._content_layout.takeAt(0)
            if item is None:
                break
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

    def _add_section(self, title: str, count: int) -> None:
        sec = _SectionLabel(title, count)
        self._content_layout.insertWidget(
            self._content_layout.count() - 1, sec)

    def _add_user_card(
        self,
        nickname: str,
        *,
        online: bool,
        is_host: bool,
        is_self: bool,
        rec: UserRecord,
    ) -> None:
        # 접속 지속 시간이나 마지막 접속 시각 같은 부가 정보는 정보 밀도를
        # 낮추려고 의도적으로 생략한다.
        status_text = i18n.t("sessions.status_online") if online else i18n.t("sessions.status_offline")
        card = _UserCard(
            nickname=nickname,
            is_host=is_host,
            is_self=is_self,
            online=online,
            status_text=status_text,
            sub_text="",
        )
        self._content_layout.insertWidget(
            self._content_layout.count() - 1, card)
