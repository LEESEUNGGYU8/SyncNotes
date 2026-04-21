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
    """Filled circle that visualizes the note's current background color."""
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(QPen(QColor(0, 0, 0, 110), 1))
    margin = 2
    painter.drawEllipse(margin, margin, size - 2 * margin, size - 2 * margin)
    painter.end()
    return QIcon(pix)
