from __future__ import annotations

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer


_SVG = {
    "plus": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        '<path d="M12 5v14M5 12h14" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" fill="none"/></svg>'
    ),
    "clock": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        '<circle cx="12" cy="12" r="9" stroke="{color}" stroke-width="2" fill="none"/>'
        '<path d="M12 7v5l3 2" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" fill="none"/></svg>'
    ),
    "eye_off": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        '<path d="M3 3l18 18" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
        '<path d="M10.5 6.2A10 10 0 0 1 12 6c6.5 0 9 6 9 6a13 13 0 0 1-3.3 3.8" '
        'stroke="{color}" stroke-width="2" stroke-linecap="round" fill="none"/>'
        '<path d="M6.3 7.4C4 9 3 12 3 12s2.5 6 9 6c1.5 0 2.8-.3 4-.8" '
        'stroke="{color}" stroke-width="2" stroke-linecap="round" fill="none"/></svg>'
    ),
    "close": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        '<path d="M6 6l12 12M18 6L6 18" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round"/></svg>'
    ),
    "eye_on": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        '<path d="M12 5C5.5 5 2.5 12 2.5 12S5 19 12 19s9.5-7 9.5-7S18 5 12 5z" '
        'stroke="{color}" stroke-width="2" fill="none" stroke-linejoin="round"/>'
        '<circle cx="12" cy="12" r="3" stroke="{color}" stroke-width="2" fill="none"/></svg>'
    ),
    "search": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        '<circle cx="10.5" cy="10.5" r="6.5" stroke="{color}" stroke-width="2" fill="none"/>'
        '<path d="M15.5 15.5l5 5" stroke="{color}" stroke-width="2" stroke-linecap="round"/></svg>'
    ),
    "more": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        '<circle cx="5" cy="12" r="1.5" fill="{color}"/>'
        '<circle cx="12" cy="12" r="1.5" fill="{color}"/>'
        '<circle cx="19" cy="12" r="1.5" fill="{color}"/></svg>'
    ),
    "link": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1" '
        'stroke="{color}" stroke-width="2" fill="none" stroke-linecap="round"/>'
        '<path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1" '
        'stroke="{color}" stroke-width="2" fill="none" stroke-linecap="round"/></svg>'
    ),
    "bold": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        '<path d="M8 5h5.5a3.5 3.5 0 0 1 0 7H8V5z" '
        'stroke="{color}" stroke-width="2" fill="none" stroke-linejoin="round"/>'
        '<path d="M8 12h6.5a3.5 3.5 0 0 1 0 7H8v-7z" '
        'stroke="{color}" stroke-width="2" fill="none" stroke-linejoin="round"/></svg>'
    ),
    "italic": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        '<path d="M10 5h8M6 19h8M14 5l-4 14" '
        'stroke="{color}" stroke-width="2" stroke-linecap="round" fill="none"/></svg>'
    ),
    "underline": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        '<path d="M7 4v8a5 5 0 0 0 10 0V4" '
        'stroke="{color}" stroke-width="2" stroke-linecap="round" fill="none"/>'
        '<path d="M6 20h12" stroke="{color}" stroke-width="2" stroke-linecap="round"/></svg>'
    ),
    "strike": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        '<path d="M17 7.5c-1.2-1.7-3-2.5-5-2.5-2.8 0-4.5 1.4-4.5 3.2 0 1.6 1.4 2.6 3.5 3.3" '
        'stroke="{color}" stroke-width="2" fill="none" stroke-linecap="round"/>'
        '<path d="M7 16c1 1.8 3 3 5.5 3 2.8 0 4.5-1.4 4.5-3.3 0-1.1-.5-1.9-1.5-2.5" '
        'stroke="{color}" stroke-width="2" fill="none" stroke-linecap="round"/>'
        '<path d="M4 12h16" stroke="{color}" stroke-width="2" stroke-linecap="round"/></svg>'
    ),
    "list": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        '<circle cx="5" cy="6" r="1.6" fill="{color}"/>'
        '<circle cx="5" cy="12" r="1.6" fill="{color}"/>'
        '<circle cx="5" cy="18" r="1.6" fill="{color}"/>'
        '<path d="M10 6h11M10 12h11M10 18h11" stroke="{color}" stroke-width="2" stroke-linecap="round"/></svg>'
    ),
    "highlight": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        '<path d="M10 14l6.5-6.5 3 3L13 17H10v-3z" stroke="{color}" '
        'stroke-width="1.9" fill="none" stroke-linejoin="round"/>'
        '<path d="M15 6.5l2.5-2.5 3 3-2.5 2.5" stroke="{color}" '
        'stroke-width="1.9" fill="none" stroke-linejoin="round"/>'
        '<path d="M5 20.5h8" stroke="{color}" stroke-width="3" '
        'stroke-linecap="round"/></svg>'
    ),
    "text_color": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        '<path d="M11 4h2l5.4 13h-2.5l-1.3-3.3H9.4L8.1 17H5.6L11 4z'
        'M10.15 11.6h3.7L12 7l-1.85 4.6z" fill="{color}" fill-rule="evenodd"/>'
        '<rect x="5" y="19.2" width="14" height="2.6" rx="1.3" fill="{color}"/></svg>'
    ),
    "image": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        '<rect x="3" y="5" width="18" height="14" rx="2.5" '
        'stroke="{color}" stroke-width="2" fill="none"/>'
        '<circle cx="9" cy="10" r="1.6" fill="{color}"/>'
        '<path d="M3.5 17.5l4.5-4 4 4 3.5-3 5 4.5" '
        'stroke="{color}" stroke-width="2" fill="none" stroke-linejoin="round"/></svg>'
    ),
    "settings": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        '<circle cx="12" cy="12" r="3.2" stroke="{color}" stroke-width="2" fill="none"/>'
        '<path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1'
        'a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1'
        'a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1'
        'a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1'
        'a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1'
        'a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1'
        'a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1'
        'a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1'
        'a1.7 1.7 0 0 0-1.5 1z" '
        'stroke="{color}" stroke-width="2" fill="none" '
        'stroke-linecap="round" stroke-linejoin="round"/></svg>'
    ),
    "users": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        '<circle cx="9" cy="9" r="3.4" stroke="{color}" stroke-width="2" fill="none"/>'
        '<path d="M3 19c0-3 2.7-5 6-5s6 2 6 5" stroke="{color}" stroke-width="2" '
        'fill="none" stroke-linecap="round"/>'
        '<path d="M16 11.4a3 3 0 1 0 0-5.8" stroke="{color}" stroke-width="2" '
        'fill="none" stroke-linecap="round"/>'
        '<path d="M17 14.2c2.4.4 4 2 4 4.3" stroke="{color}" stroke-width="2" '
        'fill="none" stroke-linecap="round"/>'
        '</svg>'
    ),
    "lock": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        '<path d="M8 11V8a4 4 0 0 1 8 0v3" stroke="{color}" stroke-width="2" '
        'fill="none" stroke-linecap="round"/>'
        '<rect x="5.5" y="11" width="13" height="9" rx="2.2" '
        'stroke="{color}" stroke-width="2" fill="none"/>'
        '<circle cx="12" cy="15" r="1.2" fill="{color}"/>'
        '</svg>'
    ),
    "folder": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z" '
        'stroke="{color}" stroke-width="2" fill="none" stroke-linejoin="round"/></svg>'
    ),
}


def svg_icon(name: str, size: int = 18, color: str = "#333333") -> QIcon:
    svg_str = _SVG[name].format(color=color)
    renderer = QSvgRenderer(QByteArray(svg_str.encode("utf-8")))
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)
    renderer.render(painter)
    painter.end()
    return QIcon(pix)


def color_swatch_icon(color: str, size: int = 18) -> QIcon:
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(color))
    try:
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)
        lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
    except (ValueError, IndexError):
        lum = 0.5
    if lum < 0.30:
        border = QColor(255, 255, 255, 110)
    else:
        border = QColor(0, 0, 0, 110)
    painter.setPen(QPen(border, 1))
    margin = 2
    painter.drawEllipse(margin, margin, size - 2 * margin, size - 2 * margin)
    painter.end()
    return QIcon(pix)
