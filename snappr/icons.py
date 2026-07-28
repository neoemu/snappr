"""Programmatically drawn toolbar icons.

No asset files: every icon is painted with ``QPainter`` at runtime using the
current palette text color, so they fit light and dark themes alike. Icons are
drawn at a large internal size and scaled down smoothly by ``QIcon``.
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QApplication

# Icons are painted at this size and scaled down by QIcon (smooth).
_SIZE = 64.0


def _foreground() -> QColor:
    app = QApplication.instance()
    if app is not None:
        return app.palette().windowText().color()
    return QColor("#202020")


def _pen(color: QColor, width: float) -> QPen:
    pen = QPen(color, width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def _make(
    paint: Callable[[QPainter, float, QColor], None],
    color: QColor | None = None,
) -> QIcon:
    fg = QColor(color) if color is not None else _foreground()
    pix = QPixmap(int(_SIZE), int(_SIZE))
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(_pen(fg, _SIZE * 0.09))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    paint(painter, _SIZE, fg)
    painter.end()
    return QIcon(pix)


def select_icon(color: QColor | None = None) -> QIcon:
    """Mouse-pointer arrow (tool: select/move)."""

    def paint(p: QPainter, s: float, fg: QColor) -> None:
        cursor = QPolygonF(
            [
                QPointF(s * 0.34, s * 0.14),
                QPointF(s * 0.34, s * 0.76),
                QPointF(s * 0.47, s * 0.63),
                QPointF(s * 0.56, s * 0.84),
                QPointF(s * 0.64, s * 0.80),
                QPointF(s * 0.55, s * 0.60),
                QPointF(s * 0.72, s * 0.60),
            ]
        )
        p.setPen(_pen(fg, s * 0.04))
        p.setBrush(fg)
        p.drawPolygon(cursor)

    return _make(paint, color)


def rect_icon(color: QColor | None = None) -> QIcon:
    """Rectangle outline (tool: rectangle)."""

    def paint(p: QPainter, s: float, fg: QColor) -> None:  # noqa: ARG001
        p.drawRoundedRect(QRectF(s * 0.16, s * 0.26, s * 0.68, s * 0.48), s * 0.06, s * 0.06)

    return _make(paint, color)


def arrow_icon(color: QColor | None = None) -> QIcon:
    """Diagonal arrow with a filled head (tool: arrow)."""

    def paint(p: QPainter, s: float, fg: QColor) -> None:
        p.drawLine(QPointF(s * 0.22, s * 0.78), QPointF(s * 0.66, s * 0.34))
        head = QPolygonF(
            [
                QPointF(s * 0.78, s * 0.22),
                QPointF(s * 0.48, s * 0.30),
                QPointF(s * 0.70, s * 0.52),
            ]
        )
        p.setPen(_pen(fg, s * 0.02))
        p.setBrush(fg)
        p.drawPolygon(head)

    return _make(paint, color)


def text_icon(color: QColor | None = None) -> QIcon:
    """Letter "T" (tool: text)."""

    def paint(p: QPainter, s: float, fg: QColor) -> None:  # noqa: ARG001
        p.drawLine(QPointF(s * 0.24, s * 0.24), QPointF(s * 0.76, s * 0.24))
        p.drawLine(QPointF(s * 0.50, s * 0.24), QPointF(s * 0.50, s * 0.78))

    return _make(paint, color)


def trash_icon(color: QColor | None = None) -> QIcon:
    """Trash bin (action: delete selection)."""

    def paint(p: QPainter, s: float, fg: QColor) -> None:  # noqa: ARG001
        # Lid and handle.
        p.drawLine(QPointF(s * 0.20, s * 0.30), QPointF(s * 0.80, s * 0.30))
        handle = QPolygonF(
            [
                QPointF(s * 0.40, s * 0.30),
                QPointF(s * 0.40, s * 0.19),
                QPointF(s * 0.60, s * 0.19),
                QPointF(s * 0.60, s * 0.30),
            ]
        )
        p.drawPolyline(handle)
        # Body and inner strokes.
        p.drawRoundedRect(QRectF(s * 0.27, s * 0.38, s * 0.46, s * 0.44), s * 0.05, s * 0.05)
        p.drawLine(QPointF(s * 0.42, s * 0.47), QPointF(s * 0.42, s * 0.72))
        p.drawLine(QPointF(s * 0.58, s * 0.47), QPointF(s * 0.58, s * 0.72))

    return _make(paint, color)


def width_icon(color: QColor | None = None) -> QIcon:
    """Three lines of growing thickness (stroke width indicator)."""

    def paint(p: QPainter, s: float, fg: QColor) -> None:
        for y, w in ((0.24, 0.05), (0.48, 0.10), (0.76, 0.16)):
            p.setPen(_pen(fg, s * w))
            p.drawLine(QPointF(s * 0.18, s * y), QPointF(s * 0.82, s * y))

    return _make(paint, color)
