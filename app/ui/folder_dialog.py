from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import config, i18n
from .icons import color_swatch_icon
from .theme import refresh_style


class FolderEditDialog(QDialog):
    def __init__(
        self,
        *,
        title: str = "새 폴더",
        name: str = "",
        color: str = config.DEFAULT_COLOR,
        private: bool = False,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(360)

        self._selected_color = color
        self._color_buttons: dict[str, QToolButton] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(12)

        name_row = QHBoxLayout()
        name_row.setSpacing(8)
        name_lbl = QLabel(i18n.t("folder.label_name"))
        name_lbl.setMinimumWidth(50)
        name_lbl.setStyleSheet("font-size: 12.5px; color: #4B5563;")
        name_row.addWidget(name_lbl)
        self._name_edit = QLineEdit(name)
        self._name_edit.setPlaceholderText(i18n.t("folder.placeholder_name"))
        self._name_edit.setMinimumHeight(30)
        name_row.addWidget(self._name_edit, 1)
        root.addLayout(name_row)

        color_lbl = QLabel(i18n.t("folder.label_color"))
        color_lbl.setStyleSheet("font-size: 12.5px; color: #4B5563;")
        root.addWidget(color_lbl)

        swatch_row = QHBoxLayout()
        swatch_row.setContentsMargins(0, 0, 0, 0)
        swatch_row.setSpacing(6)
        swatch_row.addStretch(1)
        for hex_color in config.COLORS:
            btn = QToolButton()
            btn.setFixedSize(32, 32)
            btn.setIcon(color_swatch_icon(hex_color, 24))
            btn.setIconSize(QSize(24, 24))
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFocusPolicy(Qt.NoFocus)
            btn.setStyleSheet(
                "QToolButton { border: 1px solid transparent; padding: 2px; "
                "border-radius: 7px; background: transparent; }"
                "QToolButton:hover { background: rgba(0,0,0,0.06); }"
                "QToolButton:checked { border: 2px solid #1F1F1F; }"
            )
            btn.clicked.connect(lambda _=False, c=hex_color: self._select(c))
            self._color_buttons[hex_color] = btn
            swatch_row.addWidget(btn)
        swatch_row.addStretch(1)
        root.addLayout(swatch_row)
        self._refresh_color_buttons()

        self._private_check = QCheckBox(i18n.t("folder.private_toggle"))
        self._private_check.setChecked(private)
        root.addWidget(self._private_check)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        ok = buttons.button(QDialogButtonBox.Ok)
        cancel = buttons.button(QDialogButtonBox.Cancel)
        ok.setText(i18n.t("folder.btn_save"))
        cancel.setText(i18n.t("folder.btn_cancel"))
        cancel.setProperty("secondary", True)
        refresh_style(cancel)
        ok.setMinimumWidth(110)
        cancel.setMinimumWidth(110)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _select(self, color: str) -> None:
        self._selected_color = color
        self._refresh_color_buttons()

    def _refresh_color_buttons(self) -> None:
        for c, b in self._color_buttons.items():
            b.setChecked(c == self._selected_color)

    def name(self) -> str:
        return self._name_edit.text().strip()

    def color(self) -> str:
        return self._selected_color

    def private(self) -> bool:
        return self._private_check.isChecked()
