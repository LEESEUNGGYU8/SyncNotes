from __future__ import annotations

import json
import platform
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from . import config

IMAGE_VIEWER_BUILTIN = "builtin"
IMAGE_VIEWER_SYSTEM = "system"
IMAGE_VIEWER_CHOICES = (IMAGE_VIEWER_BUILTIN, IMAGE_VIEWER_SYSTEM)


@dataclass
class AppSettings:
    # 빈 문자열 = 미선택 → 시작 시 OS 로케일을 감지해 적용한다.
    language_code: str = ""
    default_font_size: int = 11
    default_note_color: str = config.DEFAULT_COLOR
    show_tray_icon: bool = True
    close_main_to_tray: bool = True

    move_checked_to_bottom: bool = False

    # 메모 안 이미지를 더블 클릭했을 때 여는 방법.
    # "builtin" = 앱 자체 이미지 뷰어, "system" = OS 기본 이미지 뷰어(임시 파일 경유).
    image_viewer: str = IMAGE_VIEWER_BUILTIN

    autostart: bool = False

    default_port: int = config.DEFAULT_PORT
    default_heartbeat_ms: int = config.DEFAULT_HEARTBEAT_MS

    backup_enabled: bool = False
    backup_dir: str = ""                 # 빈 문자열 = app_data_dir()/backups
    backup_interval_value: int = 24
    backup_interval_unit: str = "hours"  # "minutes" | "hours" | "days"
    backup_keep_count: int = 10

    @classmethod
    def load(cls, path: Path | None = None) -> "AppSettings":
        p = path or config.default_settings_path()
        if not p.exists():
            return cls()
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            known = {k: raw[k] for k in cls.__dataclass_fields__ if k in raw}
            loaded = cls(**known)
        except (json.JSONDecodeError, TypeError, ValueError):
            return cls()
        # 손으로 고친 설정 파일의 모르는 값은 기본값으로 되돌린다.
        if loaded.image_viewer not in IMAGE_VIEWER_CHOICES:
            loaded.image_viewer = IMAGE_VIEWER_BUILTIN
        return loaded

    def save(self, path: Path | None = None) -> None:
        p = path or config.default_settings_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def resolved_backup_dir(self) -> Path:
        if self.backup_dir:
            return Path(self.backup_dir)
        return config.default_backup_dir()

    def backup_interval_seconds(self) -> int:
        v = max(1, int(self.backup_interval_value))
        unit = self.backup_interval_unit
        if unit == "minutes":
            return v * 60
        if unit == "days":
            return v * 24 * 3600
        return v * 3600


def _autostart_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    script = Path(__file__).resolve().parent.parent / "main.py"
    return f'"{sys.executable}" "{script}"'


def set_windows_autostart(enabled: bool) -> bool:
    if platform.system() != "Windows":
        return False
    try:
        import winreg
    except ImportError:
        return False
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS
        ) as key:
            if enabled:
                winreg.SetValueEx(
                    key, config.APP_NAME, 0, winreg.REG_SZ, _autostart_command())
            else:
                try:
                    winreg.DeleteValue(key, config.APP_NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False


def get_windows_autostart() -> bool:
    if platform.system() != "Windows":
        return False
    try:
        import winreg
    except ImportError:
        return False
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            winreg.QueryValueEx(key, config.APP_NAME)
            return True
    except FileNotFoundError:
        return False
    except OSError:
        return False
