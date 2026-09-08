"""메모 안 이미지를 임시 파일로 내보내 외부 뷰어로 여는 도우미.

메모 이미지는 파일이 아니라 본문 HTML 의 ``data:`` URL(base64) 로 DB 에
들어 있다. 그래서 Windows 기본 이미지 뷰어(사진 앱 등)로 열려면 먼저 바이트를
실제 파일로 풀어 놓아야 한다. 파일은 사용자 임시 폴더 아래 앱 전용 폴더에
내용 해시 이름으로 두므로 같은 이미지를 여러 번 열어도 하나만 남고, 오래된
파일은 다음 호출 때 정리한다. 원본 메모 데이터는 전혀 건드리지 않는다.

Qt 에 의존하지 않아 단위 테스트가 GUI 없이 돈다."""
from __future__ import annotations

import base64
import binascii
import hashlib
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import config

# 임시 파일 보관 시간. 외부 뷰어가 파일을 이미 읽어들인 뒤라면 지워도 무방하다.
TEMP_IMAGE_MAX_AGE_S = 24 * 3600

_MIME_EXT = {
    "png": ".png",
    "apng": ".png",
    "jpeg": ".jpg",
    "jpg": ".jpg",
    "gif": ".gif",
    "bmp": ".bmp",
    "webp": ".webp",
}


def parse_data_url(data_url: str) -> tuple[bytes, str] | None:
    """``data:image/<subtype>;base64,<payload>`` 를 ``(바이트, subtype)`` 로 푼다.

    형식이 아니거나 디코드에 실패하면 None."""
    if not data_url or not data_url.startswith("data:"):
        return None
    try:
        header, payload = data_url.split(",", 1)
    except ValueError:
        return None
    meta = header[len("data:"):]
    if ";base64" not in meta:
        return None
    mime = meta.split(";", 1)[0]
    subtype = mime.split("/", 1)[1].lower() if "/" in mime else ""
    try:
        raw = base64.b64decode(payload, validate=False)
    except (binascii.Error, ValueError):
        return None
    if not raw:
        return None
    return raw, subtype


def sniff_extension(raw: bytes, subtype_hint: str = "") -> str:
    """매직 바이트로 확장자를 정한다. 외부 뷰어는 확장자로 형식을 고르므로
    mime 표기보다 실제 바이트를 우선한다."""
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if raw[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif"
    if raw.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if raw.startswith(b"BM"):
        return ".bmp"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return ".webp"
    return _MIME_EXT.get(subtype_hint.lower(), ".png")


def temp_image_dir() -> Path:
    return Path(tempfile.gettempdir()) / config.APP_NAME / "images"


def export_to_temp(data_url: str, directory: Path | None = None) -> Path | None:
    """data URL 을 임시 파일로 저장하고 경로를 돌려준다.

    파일 이름은 내용 해시라 같은 이미지는 한 번만 쓴다. 쓰기는 임시 이름으로
    한 뒤 바꿔 넣어, 외부 뷰어가 반쯤 쓰인 파일을 여는 일이 없게 한다."""
    parsed = parse_data_url(data_url)
    if parsed is None:
        return None
    raw, subtype = parsed
    ext = sniff_extension(raw, subtype)
    target_dir = directory or temp_image_dir()
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    digest = hashlib.sha1(raw).hexdigest()[:20]
    path = target_dir / f"{digest}{ext}"
    if path.exists():
        try:
            if path.stat().st_size == len(raw):
                os.utime(path, None)
                return path
        except OSError:
            pass
    try:
        fd, tmp_name = tempfile.mkstemp(prefix=digest, suffix=".part",
                                        dir=str(target_dir))
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(raw)
            os.replace(tmp_name, path)
        finally:
            if os.path.exists(tmp_name):
                try:
                    os.remove(tmp_name)
                except OSError:
                    pass
    except OSError:
        return None
    return path


def prune_temp_images(max_age_s: int = TEMP_IMAGE_MAX_AGE_S,
                      directory: Path | None = None,
                      now: float | None = None) -> int:
    """보관 시간이 지난 임시 이미지를 지우고 지운 개수를 돌려준다.

    외부 뷰어가 아직 잡고 있는 파일은 삭제가 거부되는데, 그때는 조용히 넘긴다."""
    target_dir = directory or temp_image_dir()
    if not target_dir.is_dir():
        return 0
    cutoff = (now if now is not None else time.time()) - max_age_s
    removed = 0
    try:
        entries = list(target_dir.iterdir())
    except OSError:
        return 0
    for entry in entries:
        try:
            if not entry.is_file():
                continue
            if entry.stat().st_mtime > cutoff:
                continue
            entry.unlink()
            removed += 1
        except OSError:
            continue
    return removed


def open_with_system_viewer(path: Path) -> bool:
    """OS 가 확장자에 연결해 둔 기본 앱으로 파일을 연다. 실패하면 False."""
    try:
        if hasattr(os, "startfile"):
            os.startfile(str(path))  # type: ignore[attr-defined]
            return True
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        subprocess.Popen([opener, str(path)])
        return True
    except OSError:
        return False


def open_data_url_externally(data_url: str) -> bool:
    """임시 파일로 내보낸 뒤 기본 뷰어로 연다. 어느 단계든 실패하면 False 를
    돌려주므로 호출 측이 자체 뷰어로 물러설 수 있다."""
    prune_temp_images()
    path = export_to_temp(data_url)
    if path is None:
        return False
    return open_with_system_viewer(path)
