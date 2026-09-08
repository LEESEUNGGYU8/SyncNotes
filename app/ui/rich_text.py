from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (
    QBuffer,
    QByteArray,
    QIODevice,
    QObject,
    QPointF,
    QRect,
    QRectF,
    QTimer,
    QUrl,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QIcon,
    QImage,
    QImageReader,
    QMovie,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QTextCursor,
    QTextDocument,
    QTextFormat,
    QTextImageFormat,
)
from PySide6.QtWidgets import QLabel, QTextEdit

from .. import config


_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".apng"}


def _is_image_file(path: str) -> bool:
    return Path(path).suffix.lower() in _IMAGE_EXTS


def _data_url_payload(data_url: str) -> QByteArray:
    if not data_url or not data_url.startswith("data:"):
        return QByteArray()
    try:
        _, payload = data_url.split(",", 1)
    except ValueError:
        return QByteArray()
    return QByteArray.fromBase64(payload.encode("ascii"))


def _data_url_format_hint(data_url: str) -> str:
    try:
        mime = data_url.split(";", 1)[0].split(":", 1)[1]
        subtype = mime.split("/", 1)[1].lower()
    except (IndexError, ValueError):
        return ""
    if subtype in ("jpeg", "jpg"):
        return "JPG"
    if subtype == "apng":
        return "PNG"
    return subtype.upper()


def data_url_payload(data_url: str) -> QByteArray:
    """``data:`` URL 의 base64 본문을 바이트로 돌려준다. 아니면 빈 배열."""
    return _data_url_payload(data_url)


def data_url_image(data_url: str) -> QImage:
    """data URL 을 원본 해상도 QImage 로 디코드한다(애니메이션은 첫 프레임).
    실패하면 null 이미지."""
    img = QImage()
    ba = _data_url_payload(data_url)
    if not ba.isEmpty():
        img.loadFromData(ba)
    return img


def is_animated_data_url(data_url: str) -> bool:
    ba = _data_url_payload(data_url)
    if ba.isEmpty():
        return False
    buf = QBuffer(ba)
    buf.open(QIODevice.ReadOnly)
    reader = QImageReader()
    reader.setDecideFormatFromContent(True)
    reader.setDevice(buf)
    try:
        if not reader.canRead():
            return False
        return reader.supportsAnimation() and reader.imageCount() > 1
    finally:
        buf.close()


def image_to_data_url(image: QImage, max_width: int = config.MAX_IMAGE_WIDTH) -> str:
    if image.isNull():
        return ""
    if image.width() > max_width:
        image = image.scaledToWidth(max_width, Qt.SmoothTransformation)
    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    image.save(buf, "PNG")
    b64 = bytes(buf.data().toBase64()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def bytes_to_data_url(raw: bytes, subtype: str) -> str:
    if not raw:
        return ""
    ba = QByteArray(raw)
    b64 = bytes(ba.toBase64()).decode("ascii")
    return f"data:image/{subtype.lower()};base64,{b64}"


_CHECKBOX_URL_CACHE: dict[bool, str] = {}

# 글머리 마커와 같은 x 좌표에 정렬되도록 체크박스 글리프 왼쪽에 투명
# 패딩을 더한다.
CHECKBOX_GLYPH_SIZE = 16
CHECKBOX_LEFT_PAD = 3
CHECKBOX_WIDTH = CHECKBOX_GLYPH_SIZE + CHECKBOX_LEFT_PAD
CHECKBOX_HEIGHT = CHECKBOX_GLYPH_SIZE


def _render_checkbox_png(checked: bool) -> QByteArray:
    pix = QPixmap(CHECKBOX_WIDTH, CHECKBOX_HEIGHT)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    margin = 1.5
    size = CHECKBOX_GLYPH_SIZE
    x_off = CHECKBOX_LEFT_PAD
    rect = QRectF(x_off + margin, margin, size - 2 * margin, size - 2 * margin)
    radius = 3.5
    if checked:
        p.setBrush(QColor("#2F2F2F"))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(rect, radius, radius)
        p.setPen(QPen(QColor("#FFFFFF"), 1.8, Qt.SolidLine,
                       Qt.RoundCap, Qt.RoundJoin))
        p.drawLine(QPointF(x_off + size * 0.28, size * 0.52),
                    QPointF(x_off + size * 0.45, size * 0.70))
        p.drawLine(QPointF(x_off + size * 0.45, size * 0.70),
                    QPointF(x_off + size * 0.74, size * 0.33))
    else:
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor("#9A9A9A"), 1.4))
        p.drawRoundedRect(rect, radius, radius)
    p.end()
    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    pix.save(buf, "PNG")
    return buf.data()


def checkbox_url(checked: bool) -> str:
    cached = _CHECKBOX_URL_CACHE.get(checked)
    if cached is not None:
        return cached
    ba = _render_checkbox_png(checked)
    b64 = bytes(ba.toBase64()).decode("ascii")
    url = f"data:image/png;base64,{b64}"
    _CHECKBOX_URL_CACHE[checked] = url
    return url


def is_checkbox_url(url: str) -> bool:
    if not url:
        return False
    return url == checkbox_url(False) or url == checkbox_url(True)


BULLET_CIRCLE = "circle"
BULLET_SQUARE = "square"
BULLET_ARROW = "arrow"
BULLET_INFO = "info"

_BULLET_NAMES = (BULLET_CIRCLE, BULLET_SQUARE, BULLET_ARROW, BULLET_INFO)
_BULLET_URL_PREFIX = "x-sticky-bullet:"
_BULLET_IMAGE_CACHE: dict[str, QImage] = {}
_BULLET_FILL = QColor("#2F2F2F")


def bullet_markers() -> tuple[str, ...]:
    return _BULLET_NAMES


def bullet_url_for(name: str) -> str | None:
    if name not in _BULLET_NAMES:
        return None
    return _BULLET_URL_PREFIX + name


def url_to_bullet_name(url: str) -> str | None:
    if not url or not url.startswith(_BULLET_URL_PREFIX):
        return None
    name = url[len(_BULLET_URL_PREFIX):]
    return name if name in _BULLET_NAMES else None


def is_bullet_url(url: str) -> bool:
    return url_to_bullet_name(url) is not None


def is_marker_url(url: str) -> bool:
    return is_checkbox_url(url) or is_bullet_url(url)


def _render_bullet_icon(name: str) -> QImage:
    canvas_w = CHECKBOX_WIDTH
    canvas_h = CHECKBOX_HEIGHT
    pix = QPixmap(canvas_w, canvas_h)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)

    glyph = CHECKBOX_GLYPH_SIZE
    cx = CHECKBOX_LEFT_PAD + glyph / 2.0
    cy = glyph / 2.0

    if name == BULLET_CIRCLE:
        p.setPen(Qt.NoPen)
        p.setBrush(_BULLET_FILL)
        r = 3.6
        p.drawEllipse(QPointF(cx, cy), r, r)
    elif name == BULLET_SQUARE:
        p.setPen(Qt.NoPen)
        p.setBrush(_BULLET_FILL)
        side = 7.4
        p.drawRoundedRect(
            QRectF(cx - side / 2, cy - side / 2, side, side), 2.1, 2.1)
    elif name == BULLET_ARROW:
        pen = QPen(_BULLET_FILL, 1.85,
                    Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        hw = 2.6
        hh = 4.0
        path = QPainterPath(QPointF(cx - hw, cy - hh))
        path.lineTo(QPointF(cx + hw, cy))
        path.lineTo(QPointF(cx - hw, cy + hh))
        p.drawPath(path)
    elif name == BULLET_INFO:
        pen = QPen(_BULLET_FILL, 1.4,
                    Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        r = 5.6
        p.drawEllipse(QPointF(cx, cy), r, r)
        p.setPen(Qt.NoPen)
        p.setBrush(_BULLET_FILL)
        dot_r = 0.85
        p.drawEllipse(QPointF(cx, cy - 2.3), dot_r, dot_r)
        stem_w = 1.3
        stem_h = 3.2
        stem_top = cy - 0.6
        p.drawRoundedRect(
            QRectF(cx - stem_w / 2, stem_top, stem_w, stem_h), 0.6, 0.6)
    p.end()
    return pix.toImage()


def bullet_image(name: str) -> QImage | None:
    if name not in _BULLET_NAMES:
        return None
    cached = _BULLET_IMAGE_CACHE.get(name)
    if cached is not None:
        return cached
    img = _render_bullet_icon(name)
    _BULLET_IMAGE_CACHE[name] = img
    return img


def bullet_qicon(name: str) -> QIcon:
    """인라인 정렬용 왼쪽 패딩을 잘라내지 않으면 메뉴 아이콘 칼럼에서
    오른쪽으로 밀려 보인다."""
    img = bullet_image(name)
    if img is None or img.isNull():
        return QIcon()
    cropped = img.copy(CHECKBOX_LEFT_PAD, 0,
                       img.width() - CHECKBOX_LEFT_PAD, img.height())
    return QIcon(QPixmap.fromImage(cropped))


def register_bullet_resources(document: QTextDocument) -> None:
    for name in _BULLET_NAMES:
        url = _BULLET_URL_PREFIX + name
        img = bullet_image(name)
        if img is None or img.isNull():
            continue
        document.addResource(
            QTextDocument.ImageResource, QUrl(url), img)


_CHECKBOX_IMAGE_CACHE: dict[bool, QImage] = {}


def checkbox_image(checked: bool) -> QImage:
    cached = _CHECKBOX_IMAGE_CACHE.get(checked)
    if cached is not None:
        return cached
    raw = _render_checkbox_png(checked)
    img = QImage()
    img.loadFromData(raw)
    _CHECKBOX_IMAGE_CACHE[checked] = img
    return img


def checkbox_qicon(checked: bool) -> QIcon:
    img = checkbox_image(checked)
    cropped = img.copy(CHECKBOX_LEFT_PAD, 0,
                       img.width() - CHECKBOX_LEFT_PAD, img.height())
    return QIcon(QPixmap.fromImage(cropped))


# 마커는 블록 포맷의 커스텀 속성에 코드로 저장하고, 글리프는 paintEvent 가
# 왼쪽 여백에 직접 그린다. 텍스트에 마커 문자를 넣지 않으므로 공백 없는 CJK
# 줄도 글머리 뒤에서 끊기지 않고, 줄바꿈된 줄이 본문에 정렬된다. 블록 포맷에
# 두면 undo 로 되돌릴 수 있고, 줄 분할 시 여백과 함께 상속돼 리스트가 자연히
# 이어진다.
MARKER_PROP = QTextFormat.UserProperty + 1
MARKER_NONE = 0
MARKER_CIRCLE = 1
MARKER_SQUARE = 2
MARKER_ARROW = 3
MARKER_INFO = 4
MARKER_CHECK0 = 5
MARKER_CHECK1 = 6
MARKER_CODES = frozenset({1, 2, 3, 4, 5, 6})
BULLET_CODES = frozenset({1, 2, 3, 4})
MARKER_MARGIN = float(CHECKBOX_WIDTH + 7)

_CODE_TO_BULLET = {
    MARKER_CIRCLE: BULLET_CIRCLE, MARKER_SQUARE: BULLET_SQUARE,
    MARKER_ARROW: BULLET_ARROW, MARKER_INFO: BULLET_INFO,
}
_BULLET_TO_CODE = {v: k for k, v in _CODE_TO_BULLET.items()}


def marker_glyph(code: int):
    if code in _CODE_TO_BULLET:
        return bullet_image(_CODE_TO_BULLET[code])
    if code == MARKER_CHECK0:
        return checkbox_image(False)
    if code == MARKER_CHECK1:
        return checkbox_image(True)
    return None


def marker_url_for_code(code: int) -> str | None:
    if code in _CODE_TO_BULLET:
        return bullet_url_for(_CODE_TO_BULLET[code])
    if code == MARKER_CHECK0:
        return checkbox_url(False)
    if code == MARKER_CHECK1:
        return checkbox_url(True)
    return None


def marker_code_for_url(url: str) -> int:
    name = url_to_bullet_name(url)
    if name is not None:
        return _BULLET_TO_CODE.get(name, MARKER_NONE)
    if url == checkbox_url(False):
        return MARKER_CHECK0
    if url == checkbox_url(True):
        return MARKER_CHECK1
    return MARKER_NONE


def has_non_marker_image(html: str) -> bool:
    if not html or "<img" not in html.lower():
        return False
    import re
    pattern = re.compile(r'<img[^>]*src=["\']([^"\']+)["\']', re.IGNORECASE)
    for match in pattern.finditer(html):
        if not is_marker_url(match.group(1)):
            return True
    return False


has_non_checkbox_image = has_non_marker_image


def html_to_plain(html: str) -> str:
    if not html:
        return ""
    if "<" not in html:
        return html
    doc = QTextDocument()
    doc.setHtml(html)
    return doc.toPlainText().replace("￼", "")


# PySide6 는 QObject 서브클래스를 통해 QTextObjectInterface 가상
# 메서드를 디스패치하지 않아 커스텀 text-object 핸들러로 애니메이션
# 프레임을 그릴 수 없다. 그래서 애니메이션 이미지를 표준 ``<img
# src="data:...">`` 조각에 두고, 매 QMovie 프레임마다 QTextDocument
# 의 이미지 리소스를 교체해 구동한다.

class AnimationDriver(QObject):
    def __init__(self, host_edit: QTextEdit):
        super().__init__(host_edit)
        self._host = host_edit
        # QMovie 가 버퍼를 스트리밍하므로, 살려두지 않으면 Python 이 GC
        # 해서 재생이 끊긴다.
        self._movies: dict[str, tuple[QMovie, QBuffer]] = {}

    def known_urls(self) -> set[str]:
        return set(self._movies)

    def register(self, data_url: str) -> bool:
        """이번 호출에서 새 QMovie 를 만들었으면 True. 호출자는 Qt 가
        그리기 전에 첫 프레임을 배치하는 데 쓸 수 있다."""
        if not data_url or data_url in self._movies:
            return False
        ba = _data_url_payload(data_url)
        if ba.isEmpty():
            return False
        buf = QBuffer()
        buf.setData(ba)
        if not buf.open(QIODevice.ReadOnly):
            return False
        fmt_hint = _data_url_format_hint(data_url)
        movie = QMovie()
        movie.setDevice(buf)
        if fmt_hint:
            movie.setFormat(QByteArray(fmt_hint.encode("ascii")))
        movie.setCacheMode(QMovie.CacheAll)
        if not movie.isValid():
            buf.close()
            return False
        movie.frameChanged.connect(
            lambda _frame, u=data_url: self._on_frame_changed(u))
        self._movies[data_url] = (movie, buf)
        movie.start()
        # 최초 paint 가 원시 data URL 의 기본 디코드로 폴백하지 않도록
        # 첫 프레임을 동기적으로 넣어 둔다.
        self._swap_resource(data_url)
        return True

    def _on_frame_changed(self, data_url: str) -> None:
        self._swap_resource(data_url)

    def _swap_resource(self, data_url: str) -> None:
        entry = self._movies.get(data_url)
        if entry is None:
            return
        movie, _buf = entry
        pix = movie.currentPixmap()
        if pix.isNull():
            return
        img = pix.toImage()
        doc = self._host.document()
        doc.addResource(QTextDocument.ImageResource, QUrl(data_url), img)
        vp = self._host.viewport()
        if vp is not None:
            vp.update()

    def unregister_missing(self, current_urls: set[str]) -> None:
        stale = [u for u in self._movies if u not in current_urls]
        for url in stale:
            movie, buf = self._movies.pop(url)
            movie.stop()
            buf.close()

    def stop_all(self) -> None:
        for movie, buf in self._movies.values():
            movie.stop()
            buf.close()
        self._movies.clear()


class _MarkerAwareDocument(QTextDocument):
    """``setHtml`` 이 렌더링 전에 리소스 캐시를 비우는데, 그 사이 Qt 가
    그린 깨진 이미지 placeholder 는 리소스를 재등록해도 남는다. 글머리
    URL 을 ``loadResource`` 에서 직접 해결하면 캐시가 비어 있어도 매
    paint 가 이 메서드로 처리되어 그 문제가 사라진다."""

    def loadResource(self, resource_type, name):  # noqa: N802
        if resource_type == QTextDocument.ImageResource:
            url_str = (name.toString() if isinstance(name, QUrl)
                       else str(name))
            if is_bullet_url(url_str):
                bname = url_to_bullet_name(url_str)
                if bname is not None:
                    img = bullet_image(bname)
                    if img is not None and not img.isNull():
                        return img
        return super().loadResource(resource_type, name)


class RichTextEdit(QTextEdit):
    imageInserted = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDocument(_MarkerAwareDocument(self))
        self.setAcceptRichText(True)
        self.setAcceptDrops(True)
        self._anim = AnimationDriver(self)
        self.document().contentsChange.connect(self._on_contents_change)
        register_bullet_resources(self.document())

        # 본문 이미지의 원본 크기와 애니메이션 여부(URL → (w, h, animated)).
        # 헤더만 읽어 채우므로 전체 디코드가 없다.
        self._img_meta: dict[str, tuple[int, int, bool]] = {}
        # 문서에 등록해 둔 표시용 리소스의 픽셀 크기(URL → (w, h)). Qt 는 문서
        # 안 이미지를 최근접 방식으로 줄여 그려 큰 원본을 그대로 두면 계단이
        # 지므로, 표시 크기로 부드럽게 줄인 사본을 리소스로 넣는다. 저장 HTML
        # 에는 원본 data URL 이 그대로 남아 데이터는 바뀌지 않는다.
        self._display_res: dict[str, tuple[int, int]] = {}
        # 표시용 사본을 만들 때 쓰는 원본 디코드 캐시. 크기 조절 드래그 동안만
        # 살려 두고 곧 비워, 큰 원본이 메모(숨은 메모 포함)마다 상주하지 않게 한다.
        self._full_cache: dict[str, QImage] = {}
        self._full_cache_timer = QTimer(self)
        self._full_cache_timer.setSingleShot(True)
        self._full_cache_timer.setInterval(1500)
        self._full_cache_timer.timeout.connect(self._full_cache.clear)

        self._size_popup = QLabel(self)
        self._size_popup.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._size_popup.setAlignment(Qt.AlignCenter)
        self._size_popup.setStyleSheet(
            "background: rgba(28, 28, 28, 0.88); color: #FFFFFF; "
            "border-radius: 9px; padding: 6px 14px; "
            "font-size: 13px; font-weight: 700;"
        )
        self._size_popup.hide()
        self._size_popup_timer = QTimer(self)
        self._size_popup_timer.setSingleShot(True)
        self._size_popup_timer.timeout.connect(self._size_popup.hide)

    def _show_size_popup(self, size: int) -> None:
        self._size_popup.setText(f"{size} pt")
        self._size_popup.adjustSize()
        x = (self.width() - self._size_popup.width()) // 2
        y = (self.height() - self._size_popup.height()) // 2
        self._size_popup.move(max(4, x), max(4, y))
        self._size_popup.show()
        self._size_popup.raise_()
        self._size_popup_timer.start(900)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        """Qt 는 글머리 마커를 끌 수 있는 image-object 로 다룬다. 글머리
        좌클릭을 redirect 해 커서를 마커 바로 뒤로 보내면, 선택 가능한
        이미지가 아니라 접두 글리프처럼 동작한다. 체크박스는 redirect
        하지 않는다. StickyNoteWidget 이벤트 필터가 토글을 위해 클릭을
        가로채므로 이 메서드까지 오지 않는다."""
        if event.button() == Qt.LeftButton:
            local_pos = (event.position().toPoint()
                         if hasattr(event, "position") else event.pos())
            target = self._snap_past_bullet(local_pos)
            if target is not None:
                cursor = self.textCursor()
                anchor_mode = (
                    QTextCursor.KeepAnchor
                    if event.modifiers() & Qt.ShiftModifier
                    else QTextCursor.MoveAnchor
                )
                cursor.setPosition(target, anchor_mode)
                self.setTextCursor(cursor)
                event.accept()
                return
        super().mousePressEvent(event)

    def _snap_past_bullet(self, pos) -> int | None:
        """``pos`` 가 글머리 마커 위라면 마커와 뒤따르는 공백 다음의
        문서 위치를, 아니면 None 을 반환한다."""
        cursor = self.cursorForPosition(pos)
        block = cursor.block()
        if not block.isValid():
            return None
        # 마커 조각은 블록 맨 앞에 있다. 커서가 그보다 뒤면 이미 마커를
        # 지나온 상태라 redirect 할 필요가 없다.
        col = cursor.position() - block.position()
        if col > 1:
            return None
        it = block.begin()
        if it.atEnd():
            return None
        frag = it.fragment()
        fmt = frag.charFormat()
        if not fmt.isImageFormat():
            return None
        url = fmt.toImageFormat().name()
        if not is_bullet_url(url):
            return None
        text = block.text()
        advance = 2 if len(text) > 1 and text[1] == " " else 1
        return block.position() + advance

    def canInsertFromMimeData(self, source) -> bool:  # noqa: N802
        if source.hasImage():
            return True
        if source.hasUrls():
            for url in source.urls():
                if url.isLocalFile() and _is_image_file(url.toLocalFile()):
                    return True
        return super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source) -> None:  # noqa: N802
        # 로컬 이미지 파일 URL 을 먼저 처리해야 원본 바이트와 애니메이션
        # 프레임을 그대로 얻는다.
        if source.hasUrls():
            inserted = False
            for url in source.urls():
                if not url.isLocalFile():
                    continue
                path = url.toLocalFile()
                if _is_image_file(path):
                    if self._insert_image_from_path(path):
                        inserted = True
            if inserted:
                return

        text = source.text() if source.hasText() else ""
        raw_img = source.imageData() if source.hasImage() else None
        has_text = bool(text)
        has_image = isinstance(raw_img, QImage) and not raw_img.isNull()

        # 복사한 HTML 의 배경·폰트가 메모로 따라오지 않도록 항상 평문으로
        # 붙여넣는다. 텍스트와 이미지를 한 edit-block 에 묶어 undo/redo
        # 가 전체를 한 번에 되돌리게 한다.
        if has_text or has_image:
            cursor = self.textCursor()
            cursor.beginEditBlock()
            try:
                if has_text:
                    cursor.insertText(text)
                if has_image:
                    if has_text:
                        cursor.insertText("\n")
                    self.insert_image(raw_img)
            finally:
                cursor.endEditBlock()
            return

        super().insertFromMimeData(source)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if self.canInsertFromMimeData(event.mimeData()):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        if self.canInsertFromMimeData(event.mimeData()):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802
        if self.canInsertFromMimeData(event.mimeData()):
            self.insertFromMimeData(event.mimeData())
            event.acceptProposedAction()
            return
        super().dropEvent(event)

    def insert_image(self, image: QImage) -> None:
        data_url = image_to_data_url(image)
        if not data_url:
            return
        self.document().addResource(
            QTextDocument.ImageResource, QUrl(data_url), image)
        cursor = self.textCursor()
        cursor.beginEditBlock()
        try:
            cursor.insertHtml(f'<img src="{data_url}" />')
            self.fit_images_to_viewport()
        finally:
            cursor.endEditBlock()
        self.imageInserted.emit()

    def _insert_image_from_path(self, path: str) -> bool:
        p = Path(path)
        try:
            raw = p.read_bytes()
        except OSError:
            return False
        if not raw:
            return False
        ext = p.suffix.lstrip(".").lower()
        if ext in ("jpg", "jpeg"):
            ext = "jpeg"
        ba = QByteArray(raw)
        buf = QBuffer(ba)
        buf.open(QIODevice.ReadOnly)
        reader = QImageReader()
        reader.setDecideFormatFromContent(True)
        reader.setDevice(buf)
        is_animated = reader.supportsAnimation() and reader.imageCount() > 1
        buf.close()
        if is_animated:
            data_url = bytes_to_data_url(raw, ext)
            self._insert_animated(data_url)
        else:
            img = QImage()
            img.loadFromData(ba)
            if img.isNull():
                return False
            self.insert_image(img)
        return True

    def _insert_animated(self, data_url: str) -> None:
        if not data_url:
            return
        # Qt 가 조각을 레이아웃하기 전에 URL 에 그릴 내용이 있도록 먼저
        # 첫 프레임을 채운다.
        self._anim.register(data_url)
        cursor = self.textCursor()
        cursor.beginEditBlock()
        try:
            cursor.insertHtml(f'<img src="{data_url}" />')
            self.fit_images_to_viewport()
        finally:
            cursor.endEditBlock()
        self.imageInserted.emit()

    def setHtml(self, html: str) -> None:  # noqa: N802
        super().setHtml(html)
        # setHtml 이 리소스 캐시를 비우므로 글머리 PNG 를 다시 등록한다.
        register_bullet_resources(self.document())
        # 표시용 리소스도 함께 사라졌으므로 등록 기록을 지운다.
        self._display_res.clear()
        # setHtml 은 data: 이미지를 리소스로 디코드하지 않아, 디코드를 미리
        # 해 두지 않으면 첫 paint 전까지 빈 칸으로 보인다.
        self._restore_image_resources()
        self._register_animated_in_document()

    def _restore_image_resources(self) -> None:
        """setHtml 뒤 첫 paint 전에 이미지 리소스를 채운다.

        본문 이미지는 저장 HTML 에 적힌 표시 크기(width/height 속성)로 줄인
        사본을 넣는다. 아직 표시 전이라 뷰포트 폭을 모르지만 저장된 표시 크기가
        곧 마지막 표시 크기라 대체로 그대로 쓰이고, 표시되면 resizeEvent 의
        fit 이 필요할 때만 다시 맞춘다."""
        doc = self.document()
        if doc.isEmpty():
            return
        block = doc.begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                if frag.isValid() and frag.charFormat().isImageFormat():
                    img_fmt = frag.charFormat().toImageFormat()
                    name = img_fmt.name()
                    if name.startswith("data:"):
                        if is_marker_url(name):
                            self._restore_marker_resource(doc, name)
                        else:
                            meta = self._image_meta(name)
                            if meta is not None:
                                w, h = img_fmt.width(), img_fmt.height()
                                if w <= 0 or h <= 0:
                                    w, h = meta[0], meta[1]
                                self._set_display_resource(
                                    name, int(round(w)), int(round(h)))
                it += 1
            block = block.next()

    def _restore_marker_resource(self, doc: QTextDocument, name: str) -> None:
        existing = doc.resource(QTextDocument.ImageResource, QUrl(name))
        if isinstance(existing, QImage) and not existing.isNull():
            return
        ba = _data_url_payload(name)
        if ba.isEmpty():
            return
        img = QImage()
        img.loadFromData(ba)
        if not img.isNull():
            doc.addResource(QTextDocument.ImageResource, QUrl(name), img)

    def _image_meta(self, data_url: str) -> tuple[int, int, bool] | None:
        """``(원본 폭, 원본 높이, 애니메이션 여부)``. 헤더만 읽어 캐시한다."""
        cached = self._img_meta.get(data_url)
        if cached is not None:
            return cached
        ba = _data_url_payload(data_url)
        if ba.isEmpty():
            return None
        buf = QBuffer(ba)
        buf.open(QIODevice.ReadOnly)
        reader = QImageReader()
        reader.setDecideFormatFromContent(True)
        reader.setDevice(buf)
        try:
            if not reader.canRead():
                return None
            size = reader.size()
            animated = reader.supportsAnimation() and reader.imageCount() > 1
        finally:
            buf.close()
        if not size.isValid() or size.width() <= 0 or size.height() <= 0:
            # 크기를 헤더에서 못 주는 형식이면 한 번 디코드한다.
            img = QImage()
            img.loadFromData(ba)
            if img.isNull():
                return None
            size = img.size()
        meta = (size.width(), size.height(), bool(animated))
        self._img_meta[data_url] = meta
        return meta

    def _full_image(self, data_url: str) -> QImage | None:
        img = self._full_cache.get(data_url)
        if img is None:
            img = data_url_image(data_url)
            if img.isNull():
                return None
            self._full_cache[data_url] = img
        self._full_cache_timer.start()
        return img

    def _set_display_resource(self, data_url: str, w: int, h: int) -> None:
        """``data_url`` 이미지를 논리 크기 ``w x h`` 로 그릴 때 쓸 리소스를
        등록한다. 원본보다 키우지 않고, 고해상도 화면에서는 배율만큼 더 큰
        사본을 둔다. 애니메이션은 드라이버가 프레임을 넣으므로 건드리지 않는다."""
        meta = self._image_meta(data_url)
        if meta is None or w <= 0 or h <= 0:
            return
        ow, oh, animated = meta
        if animated:
            return
        dpr = max(1.0, float(self.devicePixelRatioF()))
        tw = max(1, min(ow, int(round(w * dpr))))
        th = max(1, min(oh, int(round(h * dpr))))
        if self._display_res.get(data_url) == (tw, th):
            return
        full = self._full_image(data_url)
        if full is None:
            return
        if (tw, th) == (ow, oh):
            img = full
        else:
            img = full.scaled(tw, th, Qt.IgnoreAspectRatio,
                              Qt.SmoothTransformation)
        self.document().addResource(
            QTextDocument.ImageResource, QUrl(data_url), img)
        self._display_res[data_url] = (tw, th)

    def _register_animated_in_document(self) -> None:
        doc = self.document()
        if doc.isEmpty():
            return
        current_urls: set[str] = set()
        block = doc.begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                if frag.isValid():
                    fmt = frag.charFormat()
                    if fmt.isImageFormat():
                        url = fmt.toImageFormat().name()
                        current_urls.add(url)
                        if is_animated_data_url(url):
                            self._anim.register(url)
                it += 1
            block = block.next()
        self._anim.unregister_missing(current_urls)

    def content_image_urls(self) -> list[str]:
        """본문 이미지(글머리·체크박스 마커 제외)의 URL 을 문서 순서대로 돌려준다.

        같은 이미지를 나란히 두 번 넣으면 Qt 가 한 조각으로 합치므로, 조각
        하나가 아니라 조각 안의 글자 수만큼 센다."""
        urls: list[str] = []
        doc = self.document()
        block = doc.begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                if frag.isValid():
                    fmt = frag.charFormat()
                    if fmt.isImageFormat():
                        name = fmt.toImageFormat().name()
                        if name and not is_marker_url(name):
                            urls.extend([name] * max(1, frag.length()))
                it += 1
            block = block.next()
        return urls

    def content_image_at(self, pos) -> tuple[str, int] | None:
        """뷰포트 좌표 ``pos`` 위에 그려진 본문 이미지를 찾아 ``(URL, 본문
        이미지 순번)`` 을 돌려준다. 이미지가 아니면 None.

        ``cursorForPosition`` 은 클릭 지점에서 가장 가까운 문서 위치를 주므로
        이미지 왼쪽 절반을 누르면 이미지 앞, 오른쪽 절반이면 뒤 위치가 온다.
        두 이웃 글자를 모두 살피되, 그림이 실제로 차지하는 사각형 안일 때만
        맞은 것으로 본다(이미지 옆 글자를 더블 클릭한 경우를 걸러 낸다)."""
        doc = self.document()
        if doc.isEmpty():
            return None
        anchor = self.cursorForPosition(pos).position()
        for start in (anchor - 1, anchor):
            if start < 0:
                continue
            block = doc.findBlock(start)
            if not block.isValid():
                continue
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                it += 1
                if not frag.isValid() or not frag.contains(start):
                    continue
                fmt = frag.charFormat()
                if not fmt.isImageFormat():
                    break
                img_fmt = fmt.toImageFormat()
                name = img_fmt.name()
                if not name or is_marker_url(name):
                    break
                rect = self._image_rect_at(start, img_fmt)
                if rect is not None and rect.contains(pos):
                    return name, self._image_ordinal(start)
                break
        return None

    def _image_rect_at(self, position: int, img_fmt: QTextImageFormat):
        """문서 위치 ``position`` 의 이미지 한 장이 뷰포트에서 차지하는 사각형."""
        width = img_fmt.width()
        if width <= 0:
            meta = self._image_meta(img_fmt.name())
            if meta is not None:
                width = float(meta[0])
        if width <= 0:
            return None
        cur = QTextCursor(self.document())
        cur.setPosition(position)
        line = self.cursorRect(cur)
        return QRect(line.left(), line.top(),
                     max(1, int(round(width))), max(1, line.height()))

    def _image_ordinal(self, position: int) -> int:
        """``position`` 의 이미지가 본문 이미지 목록에서 몇 번째인지(0 기준)."""
        ordinal = 0
        doc = self.document()
        block = doc.begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                it += 1
                if not frag.isValid():
                    continue
                fmt = frag.charFormat()
                if not fmt.isImageFormat():
                    continue
                name = fmt.toImageFormat().name()
                if not name or is_marker_url(name):
                    continue
                if frag.contains(position):
                    return ordinal + (position - frag.position())
                ordinal += max(1, frag.length())
            block = block.next()
        return 0

    def _available_image_width(self) -> int:
        ml, _, mr, _ = config.TEXT_MARGINS
        return max(60, self.viewport().width() - ml - mr - 4)

    def fit_images_to_viewport(self) -> None:
        """``beginEditBlock`` 으로 묶어 기존 undo 이력을 보존한다. 스택을
        비우는 ``setUndoRedoEnabled(False)`` 방식과 의도적으로 다르다."""
        doc = self.document()
        if doc.isEmpty():
            return
        avail = self._available_image_width()
        changes: list[tuple[int, int, QTextImageFormat]] = []
        block = doc.begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                if frag.isValid():
                    fmt = frag.charFormat()
                    if fmt.isImageFormat():
                        img_fmt = fmt.toImageFormat()
                        target = self._fit_target(img_fmt, avail)
                        if target is not None:
                            new_w, new_h = target
                            # 표시 크기가 그대로여도 리소스가 아직 원본이면
                            # (방금 삽입) 표시용 사본으로 바꾼다.
                            self._set_display_resource(
                                img_fmt.name(), new_w, new_h)
                            new_fmt = self._fit_image_format(
                                img_fmt, new_w, new_h)
                            if new_fmt is not None:
                                changes.append(
                                    (frag.position(), frag.length(), new_fmt))
                it += 1
            block = block.next()
        if not changes:
            return
        cur = QTextCursor(doc)
        cur.beginEditBlock()
        try:
            for pos, length, new_fmt in changes:
                cur.setPosition(pos)
                cur.setPosition(pos + length, QTextCursor.KeepAnchor)
                cur.setCharFormat(new_fmt)
        finally:
            cur.endEditBlock()

    def _fit_target(self, img_fmt: QTextImageFormat,
                    avail: int) -> tuple[int, int] | None:
        """뷰포트 폭 ``avail`` 에 맞춘 표시 크기. 원본보다 키우지 않는다."""
        name = img_fmt.name()
        # 마커 아이콘은 본래 캔버스 크기를 유지해야 하며 사진처럼 뷰포트에
        # 맞춰 스케일되면 안 된다.
        if not name or is_marker_url(name):
            return None
        meta = self._image_meta(name)
        if meta is None:
            return None
        orig_w, orig_h, _animated = meta
        if orig_w <= 0:
            return None
        new_w = min(orig_w, avail)
        scale = new_w / orig_w
        new_h = max(1, int(round(orig_h * scale)))
        return new_w, new_h

    @staticmethod
    def _fit_image_format(img_fmt: QTextImageFormat, new_w: int,
                          new_h: int) -> QTextImageFormat | None:
        if (abs(img_fmt.width() - new_w) < 0.5
                and abs(img_fmt.height() - new_h) < 0.5):
            return None
        out = QTextImageFormat(img_fmt)
        out.setWidth(float(new_w))
        out.setHeight(float(new_h))
        return out

    def _on_contents_change(self, position: int, removed: int, added: int) -> None:
        if removed > 0 and self._anim.known_urls():
            current: set[str] = set()
            doc = self.document()
            block = doc.begin()
            while block.isValid():
                it = block.begin()
                while not it.atEnd():
                    frag = it.fragment()
                    if frag.isValid() and frag.charFormat().isImageFormat():
                        current.add(frag.charFormat().toImageFormat().name())
                    it += 1
                block = block.next()
            self._anim.unregister_missing(current)
        if added <= 0:
            return
        doc = self.document()
        cur = QTextCursor(doc)
        cur.setPosition(position)
        cur.setPosition(position + added, QTextCursor.KeepAnchor)
        fmt = cur.charFormat()
        # 표시 전 setHtml 로 이미지가 들어오면 뷰포트 폭이 작아 과하게
        # 줄어들므로, 표시된 동안의 삽입에서만 맞춘다.
        if ((fmt.isImageFormat() or "￼" in cur.selection().toPlainText())
                and self.isVisible()):
            self.fit_images_to_viewport()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        # 표시 전에는 뷰포트 폭이 확정되지 않아 이미지를 과하게 줄인다.
        # 표시된 뒤의 resize 에서만 맞춘다.
        if self.isVisible():
            self.fit_images_to_viewport()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        doc = self.document()
        block = doc.begin()
        painter = None
        while block.isValid():
            code = block.blockFormat().intProperty(MARKER_PROP)
            if code in MARKER_CODES:
                glyph = marker_glyph(code)
                if glyph is not None and not glyph.isNull():
                    cursor = QTextCursor(block)
                    cursor.setPosition(block.position())
                    r = self.cursorRect(cursor)
                    if painter is None:
                        painter = QPainter(self.viewport())
                    gx = r.left() - MARKER_MARGIN
                    gy = r.top() + (r.height() - glyph.height()) / 2.0
                    painter.drawImage(int(round(gx)), int(round(gy)), glyph)
            block = block.next()
        if painter is not None:
            painter.end()

    def wheelEvent(self, event) -> None:  # noqa: N802
        if self.isReadOnly():
            super().wheelEvent(event)
            return
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta == 0:
                event.accept()
                return
            current = self.fontPointSize()
            if current <= 0:
                current = self.document().defaultFont().pointSize() or 11
            step = 1 if delta > 0 else -1
            new_size = max(6, min(96, int(round(current)) + step))
            self.setFontPointSize(float(new_size))
            self._show_size_popup(new_size)
            event.accept()
            return
        super().wheelEvent(event)
