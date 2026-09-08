import base64
import os
import time

from app import image_export

_PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)
_GIF_1PX = base64.b64decode(
    "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
)


def _url(raw: bytes, subtype: str) -> str:
    return f"data:image/{subtype};base64," + base64.b64encode(raw).decode("ascii")


def test_parse_data_url_roundtrip():
    parsed = image_export.parse_data_url(_url(_PNG_1PX, "png"))
    assert parsed is not None
    raw, subtype = parsed
    assert raw == _PNG_1PX
    assert subtype == "png"


def test_parse_rejects_non_data_urls():
    assert image_export.parse_data_url("") is None
    assert image_export.parse_data_url("x-sticky-bullet:circle") is None
    assert image_export.parse_data_url("data:image/png,notbase64") is None
    assert image_export.parse_data_url("data:image/png;base64,") is None


def test_sniff_prefers_magic_bytes_over_mime():
    # 확장자 판정은 mime 표기가 아니라 실제 바이트를 따른다.
    assert image_export.sniff_extension(_GIF_1PX, "png") == ".gif"
    assert image_export.sniff_extension(_PNG_1PX, "gif") == ".png"
    assert image_export.sniff_extension(b"\xff\xd8\xff\xe0", "") == ".jpg"
    assert image_export.sniff_extension(b"RIFF\x00\x00\x00\x00WEBPVP8 ", "") == ".webp"
    assert image_export.sniff_extension(b"BM\x00", "") == ".bmp"
    # 모르는 바이트면 mime 힌트, 그것도 없으면 png.
    assert image_export.sniff_extension(b"????", "jpeg") == ".jpg"
    assert image_export.sniff_extension(b"????", "apng") == ".png"
    assert image_export.sniff_extension(b"????", "") == ".png"


def test_export_writes_once_and_reuses(tmp_path):
    url = _url(_PNG_1PX, "png")
    first = image_export.export_to_temp(url, directory=tmp_path)
    assert first is not None
    assert first.parent == tmp_path
    assert first.suffix == ".png"
    assert first.read_bytes() == _PNG_1PX

    second = image_export.export_to_temp(url, directory=tmp_path)
    assert second == first
    # 임시 조각(.part) 이 남지 않는다.
    assert sorted(p.name for p in tmp_path.iterdir()) == [first.name]


def test_export_uses_sniffed_extension(tmp_path):
    # mime 이 png 라고 적혀 있어도 바이트가 GIF 면 .gif 로 저장한다.
    path = image_export.export_to_temp(_url(_GIF_1PX, "png"), directory=tmp_path)
    assert path is not None
    assert path.suffix == ".gif"


def test_export_rejects_invalid(tmp_path):
    assert image_export.export_to_temp("not a data url", directory=tmp_path) is None
    assert list(tmp_path.iterdir()) == []


def test_prune_removes_only_old_files(tmp_path):
    old = tmp_path / "old.png"
    fresh = tmp_path / "fresh.png"
    old.write_bytes(_PNG_1PX)
    fresh.write_bytes(_PNG_1PX)
    now = time.time()
    os.utime(old, (now - 3 * 3600, now - 3 * 3600))
    os.utime(fresh, (now, now))

    removed = image_export.prune_temp_images(
        max_age_s=3600, directory=tmp_path, now=now)
    assert removed == 1
    assert not old.exists()
    assert fresh.exists()


def test_prune_missing_dir_is_noop(tmp_path):
    assert image_export.prune_temp_images(directory=tmp_path / "nope") == 0


def test_open_data_url_externally_falls_back_on_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(image_export, "temp_image_dir", lambda: tmp_path)
    calls: list[str] = []

    def fake_open(path):
        calls.append(str(path))
        return True

    monkeypatch.setattr(image_export, "open_with_system_viewer", fake_open)
    assert image_export.open_data_url_externally(_url(_PNG_1PX, "png")) is True
    assert len(calls) == 1
    assert calls[0].endswith(".png")

    # 잘못된 URL 은 파일을 만들지 않고 False.
    assert image_export.open_data_url_externally("garbage") is False
    assert len(calls) == 1
