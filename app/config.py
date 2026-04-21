from pathlib import Path

APP_NAME = "SyncNotes"

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESOURCE_DIR = _PROJECT_ROOT / "Resources"
FONT_PATH = (RESOURCE_DIR / "Font" / "Pretendard" / "public" / "variable"
             / "PretendardVariable.ttf")
FONT_FALLBACK_FAMILY = "Pretendard"
ICON_PATH = RESOURCE_DIR / "Image" / "Icon.png"

COLORS = [
    "#FFE066",  # yellow
    "#FFB3BA",  # pink
    "#BAFFC9",  # green
    "#BAE1FF",  # blue
    "#E0BBE4",  # purple
    "#FFD9A6",  # orange
]
DEFAULT_COLOR = COLORS[0]

DEFAULT_HEARTBEAT_MS = 3000
DEFAULT_PORT = 5555

DEFAULT_NOTE_WIDTH = 240
DEFAULT_NOTE_HEIGHT = 200
MIN_NOTE_WIDTH = 180
MIN_NOTE_HEIGHT = 120

TEXT_MARGINS = (16, 8, 16, 16)  # left, top, right, bottom (px)
HANDLE_BAR_HEIGHT = 28
RESIZE_GRIP_SIZE = 12
CORNER_RADIUS = 8

LOCK_IDLE_TIMEOUT_MS = 5 * 60 * 1000  # 5 minutes


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
