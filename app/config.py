import sys
from pathlib import Path

APP_NAME = "SyncNotes"
# 앱 버전의 단일 출처. 자동 업데이트가 이 값을 GitHub 릴리스 태그와 비교한다.
APP_VERSION = "1.0.6"

# 포크해서 다른 곳에 배포하려면 이 두 값만 바꾼다.
UPDATE_REPO_OWNER = "LEESEUNGGYU8"
UPDATE_REPO_NAME = "SyncNotes-releases"


def _resource_root() -> Path:
    """런타임에 Resources 폴더가 위치하는 디렉토리를 반환.

    * 개발 모드: 프로젝트 루트(``app`` 패키지의 부모).
    * PyInstaller 번들 내부: 압축 해제 디렉토리(``sys._MEIPASS``).
      ``--add-data "Resources;Resources"``로 넣은 리소스가 여기 있다.
    """
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
    return Path(__file__).resolve().parent.parent


_PROJECT_ROOT = _resource_root()
RESOURCE_DIR = _PROJECT_ROOT / "Resources"
_FONT_DIR = RESOURCE_DIR / "Font" / "Pretendard"
FONT_PATH = _FONT_DIR / "PretendardVariable.ttf"
FONT_PATH_JP = _FONT_DIR / "PretendardJPVariable.ttf"
FONT_FALLBACK_FAMILY = "Pretendard"
ICON_PATH = RESOURCE_DIR / "Image" / "Icon.png"

COLORS = [
    "#FFE066",
    "#FFB3BA",
    "#BAFFC9",
    "#BAE1FF",
    "#E0BBE4",
    "#FFD9A6",
    "#F5F5F5",
    "#3A3A3A",
]
DEFAULT_COLOR = COLORS[0]

DEFAULT_HEARTBEAT_MS = 3000
DEFAULT_PORT = 5555

DEFAULT_NOTE_WIDTH = 280
DEFAULT_NOTE_HEIGHT = 260
MIN_NOTE_WIDTH = 220
MIN_NOTE_HEIGHT = 180
# 첨부 시 이 폭을 넘는 이미지는 여기까지 줄여 저장한다. 1920 은 FHD 스크린샷이
# 손실 없이 들어가는 폭이다(2026-09 이전에는 520 이었고, 이미지 뷰어에서 크게 볼
# 수 있도록 올렸다). 메모 안 표시는 RichTextEdit 이 표시 크기로 따로 줄여 그린다.
MAX_IMAGE_WIDTH = 1920
FORMAT_BAR_HEIGHT = 36

TEXT_MARGINS = (18, 10, 18, 18)  # 좌, 상, 우, 하 (px)
HANDLE_BAR_HEIGHT = 32
RESIZE_GRIP_SIZE = 12
CORNER_RADIUS = 12

LOCK_IDLE_TIMEOUT_MS = 5 * 60 * 1000


def app_data_dir() -> Path:
    import os
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_db_path() -> Path:
    return app_data_dir() / "notes.sqlite3"


def default_local_state_path() -> Path:
    return app_data_dir() / "local_state.json"


def default_settings_path() -> Path:
    return app_data_dir() / "settings.json"


def default_backup_dir() -> Path:
    return app_data_dir() / "backups"
