"""본문 이미지 판정(이미지 뷰어 진입점)과 표시용 축소 리소스 테스트.
화면 없이 offscreen 플랫폼으로 돈다."""
from __future__ import annotations

import base64
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QUrl  # noqa: E402
from PySide6.QtGui import QColor, QImage, QTextCursor, QTextDocument  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app import config  # noqa: E402
from app.ui.rich_text import (  # noqa: E402
    RichTextEdit,
    bullet_url_for,
    checkbox_url,
    data_url_image,
    image_to_data_url,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _solid(w: int, h: int, color: str) -> QImage:
    img = QImage(w, h, QImage.Format_ARGB32)
    img.fill(QColor(color))
    return img


def _checker(w: int, h: int) -> QImage:
    """1px 흑백 체커보드. 부드럽게 줄이면 회색, 최근접이면 흑백만 남는다."""
    img = QImage(w, h, QImage.Format_RGB32)
    black, white = 0xFF000000, 0xFFFFFFFF
    for y in range(h):
        for x in range(w):
            img.setPixel(x, y, black if (x + y) % 2 == 0 else white)
    return img


def _image_positions(edit: RichTextEdit) -> list[int]:
    doc = edit.document()
    out: list[int] = []
    block = doc.begin()
    while block.isValid():
        it = block.begin()
        while not it.atEnd():
            frag = it.fragment()
            if frag.charFormat().isImageFormat():
                out.extend(range(frag.position(),
                                 frag.position() + frag.length()))
            it += 1
        block = block.next()
    return out


def _image_format_at(edit: RichTextEdit, pos: int):
    cur = QTextCursor(edit.document())
    cur.setPosition(pos + 1)
    return cur.charFormat().toImageFormat()


def test_data_url_image_roundtrip(qapp):
    url = image_to_data_url(_solid(40, 30, "#FF0000"))
    img = data_url_image(url)
    assert not img.isNull()
    assert (img.width(), img.height()) == (40, 30)
    assert data_url_image("x-sticky-bullet:circle").isNull()


def test_image_to_data_url_keeps_up_to_max_width(qapp):
    # 저장 폭 상한까지는 원본 그대로, 넘으면 상한 폭으로 줄인다.
    keep = data_url_image(image_to_data_url(_solid(1600, 900, "#123456")))
    assert (keep.width(), keep.height()) == (1600, 900)
    big = data_url_image(image_to_data_url(_solid(2600, 1300, "#123456")))
    assert big.width() == config.MAX_IMAGE_WIDTH
    assert big.height() == round(1300 * config.MAX_IMAGE_WIDTH / 2600)


def test_content_image_urls_skips_markers_and_counts_duplicates(qapp):
    edit = RichTextEdit()
    a = image_to_data_url(_solid(120, 80, "#00FF00"))
    b = image_to_data_url(_solid(60, 60, "#0000FF"))
    # 체크박스·글머리 마커는 본문 이미지가 아니다. 같은 이미지가 나란히 두 번
    # 오면 Qt 가 한 조각으로 합치는데 그래도 두 장으로 세야 한다.
    edit.setHtml(
        f'<p><img src="{checkbox_url(False)}" /> 할 일</p>'
        f'<p><img src="{a}" /></p>'
        f'<p><img src="{bullet_url_for("circle")}" /> 항목</p>'
        f'<p><img src="{b}" /><img src="{b}" /></p>'
    )
    urls = edit.content_image_urls()
    assert urls == [a, b, b]


def test_content_image_at_hits_image_and_misses_text(qapp):
    edit = RichTextEdit()
    edit.resize(400, 400)
    edit.show()
    qapp.processEvents()
    a = image_to_data_url(_solid(200, 120, "#00FF00"))
    b = image_to_data_url(_solid(100, 100, "#0000FF"))
    edit.setHtml(f"<p>머리글</p><p><img src=\"{a}\" /></p><p>중간</p>"
                 f"<p><img src=\"{b}\" /></p>")
    edit.fit_images_to_viewport()
    qapp.processEvents()
    positions = _image_positions(edit)
    assert len(positions) == 2

    def rect_for(pos: int):
        cur = QTextCursor(edit.document())
        cur.setPosition(pos)
        return edit.cursorRect(cur)

    r_a = rect_for(positions[0])
    r_b = rect_for(positions[1])
    # 이미지 안쪽 좌표 → 그 이미지와 순번
    hit_a = edit.content_image_at(QPoint(r_a.left() + 30, r_a.top() + 20))
    assert hit_a == (a, 0)
    hit_b = edit.content_image_at(QPoint(r_b.left() + 10, r_b.top() + 10))
    assert hit_b == (b, 1)
    # 첫 줄 텍스트 위 좌표 → None
    first = rect_for(0)
    assert edit.content_image_at(QPoint(first.left() + 4, first.top() + 4)) is None
    # 이미지 오른쪽 빈 공간(같은 줄이지만 그림 밖) → None
    assert edit.content_image_at(
        QPoint(r_a.left() + 200 + 60, r_a.top() + 10)) is None


def test_content_image_at_on_empty_document(qapp):
    edit = RichTextEdit()
    assert edit.content_image_at(QPoint(5, 5)) is None
    assert edit.content_image_urls() == []


def test_display_resource_is_downscaled_copy_and_grows_back(qapp):
    """큰 원본은 표시 크기로 줄인 사본이 리소스가 되고, 원본 크기는 따로
    기억해 메모를 넓히면 다시 커진다. 저장 HTML 의 data URL 은 그대로다."""
    edit = RichTextEdit()
    edit.resize(400, 400)
    edit.show()
    qapp.processEvents()
    url = image_to_data_url(_solid(1600, 800, "#336699"))
    edit.setHtml(f'<p><img src="{url}" /></p>')
    edit.fit_images_to_viewport()
    qapp.processEvents()

    pos = _image_positions(edit)[0]
    fmt = _image_format_at(edit, pos)
    shown_w = int(round(fmt.width()))
    assert 0 < shown_w < 1600
    res = edit.document().resource(QTextDocument.ImageResource, QUrl(url))
    assert isinstance(res, QImage) and not res.isNull()
    assert res.width() == shown_w
    assert res.height() == int(round(fmt.height()))
    # 원본 크기는 메타에 남는다.
    assert edit._image_meta(url)[:2] == (1600, 800)
    # 저장 HTML 에는 원본 data URL 이 그대로 있다.
    assert url in edit.document().toHtml()

    # 넓히면 표시 크기와 리소스가 함께 커지되 원본을 넘지 않는다.
    edit.resize(2400, 600)
    qapp.processEvents()
    edit.fit_images_to_viewport()
    qapp.processEvents()
    fmt2 = _image_format_at(edit, pos)
    assert int(round(fmt2.width())) == 1600
    res2 = edit.document().resource(QTextDocument.ImageResource, QUrl(url))
    assert (res2.width(), res2.height()) == (1600, 800)


def test_display_resource_is_smoothly_scaled(qapp):
    """최근접 축소면 체커보드가 흑백으로만 남고, 부드러운 축소면 회색이 된다."""
    edit = RichTextEdit()
    edit.resize(300, 300)
    edit.show()
    qapp.processEvents()
    url = image_to_data_url(_checker(800, 400))
    edit.setHtml(f'<p><img src="{url}" /></p>')
    edit.fit_images_to_viewport()
    qapp.processEvents()
    res = edit.document().resource(QTextDocument.ImageResource, QUrl(url))
    assert isinstance(res, QImage) and res.width() < 800
    center = QColor(res.pixel(res.width() // 2, res.height() // 2))
    assert 40 < center.red() < 215, center.red()


def test_restore_uses_saved_display_size_without_full_decode(qapp):
    """저장 HTML 의 width/height 로 첫 리소스를 만들고, 원본 캐시는 타이머가 비운다."""
    edit = RichTextEdit()
    url = image_to_data_url(_solid(1200, 600, "#AA3311"))
    edit.setHtml(f'<p><img src="{url}" width="240" height="120" /></p>')
    res = edit.document().resource(QTextDocument.ImageResource, QUrl(url))
    assert isinstance(res, QImage)
    assert (res.width(), res.height()) == (240, 120)
    assert url in edit._full_cache
    edit._full_cache_timer.stop()
    edit._full_cache.clear()
    assert edit._image_meta(url)[:2] == (1200, 600)


_PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


def test_data_url_image_decodes_raw_png(qapp):
    url = "data:image/png;base64," + base64.b64encode(_PNG_1PX).decode("ascii")
    img = data_url_image(url)
    assert not img.isNull()
    assert (img.width(), img.height()) == (1, 1)
