from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .. import config, i18n
from .theme import RoundedScrollBar, refresh_style


class UpdateAvailableDialog(QDialog):
    def __init__(
        self,
        *,
        current_version: str,
        info: dict,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(i18n.t("update_dlg.window_title"))
        self.setMinimumWidth(460)
        self.setMinimumHeight(380)

        new_version = str(info.get("version") or "")
        notes = (info.get("notes") or "").strip()

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(14)

        eyebrow = QLabel(i18n.t("update_dlg.eyebrow"))
        eyebrow.setStyleSheet(
            "color: #6B7280; font-size: 10.5px; font-weight: 700; "
            "letter-spacing: 0.6px;")
        root.addWidget(eyebrow)

        headline = QLabel(f"{config.APP_NAME} {new_version}")
        headline.setStyleSheet(
            "color: #111827; font-size: 20px; font-weight: 800;")
        root.addWidget(headline)

        sub = QLabel(i18n.t("update_dlg.current_version", version=current_version))
        sub.setStyleSheet(
            "color: #4B5563; font-size: 12px; font-weight: 600;")
        root.addWidget(sub)

        panel_label = QLabel(i18n.t("update_dlg.changes"))
        panel_label.setStyleSheet(
            "color: #1F2937; font-size: 12px; font-weight: 700; "
            "margin-top: 4px;")
        root.addWidget(panel_label)

        panel = QFrame()
        panel.setObjectName("UpdateNotesPanel")
        panel.setStyleSheet(
            "QFrame#UpdateNotesPanel { background: #F8F9FB; "
            "border: 1px solid #E5E7EB; border-radius: 10px; }"
        )
        panel_v = QVBoxLayout(panel)
        panel_v.setContentsMargins(2, 2, 2, 2)
        panel_v.setSpacing(0)

        # 내부 위젯의 QSS 테두리와 배경을 제거해, 부모 프레임의 둥근 모서리를
        # 시각적 경계로 쓴다.
        self._notes_box = QPlainTextEdit()
        self._notes_box.setReadOnly(True)
        self._notes_box.setVerticalScrollBar(RoundedScrollBar())
        self._notes_box.setFrameShape(QPlainTextEdit.NoFrame)
        self._notes_box.setStyleSheet(
            "QPlainTextEdit { background: transparent; border: none; "
            "color: #1F2937; font-size: 12.5px; padding: 10px 12px; }"
        )
        self._notes_box.setPlainText(
            notes if notes else i18n.t("update_dlg.no_notes"))
        self._notes_box.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._notes_box.setVerticalScrollBarPolicy(
            Qt.ScrollBarAsNeeded)
        panel_v.addWidget(self._notes_box)
        root.addWidget(panel, 1)

        hint = QLabel(i18n.t("update_dlg.integrity_hint"))
        hint.setStyleSheet(
            "color: #6B7280; font-size: 10.5px;")
        hint.setWordWrap(True)
        root.addWidget(hint)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        button_row.addStretch(1)

        self._later_btn = QPushButton(i18n.t("update_dlg.btn_later"))
        self._later_btn.setProperty("secondary", True)
        refresh_style(self._later_btn)
        self._later_btn.setMinimumWidth(110)
        self._later_btn.setCursor(Qt.PointingHandCursor)
        self._later_btn.clicked.connect(self.reject)
        button_row.addWidget(self._later_btn)

        self._update_btn = QPushButton(i18n.t("update_dlg.btn_now"))
        self._update_btn.setDefault(True)
        self._update_btn.setMinimumWidth(140)
        self._update_btn.setCursor(Qt.PointingHandCursor)
        self._update_btn.clicked.connect(self.accept)
        button_row.addWidget(self._update_btn)

        root.addLayout(button_row)
