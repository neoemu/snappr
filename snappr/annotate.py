"""Editable annotation canvas shown in the preview window.

The capture is placed as a non-interactive background pixmap (z=0) inside a
``QGraphicsScene``; each annotation (rectangle, arrow, text) is a
``QGraphicsItem`` stacked on top. Using ``QGraphicsView`` gives us selection,
moving, z-order and flattening (render-to-image) for free.
"""
from __future__ import annotations

import math
from enum import Enum, auto

import numpy as np
from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QImage,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
    QPixmap,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
)

from . import imageutil

# Default arrow head size relative to the pen width.
_ARROW_HEAD_LEN = 18.0
_ARROW_HEAD_ANGLE = math.radians(28.0)


class Tool(Enum):
    """Active annotation tool."""

    SELECT = auto()
    RECT = auto()
    ARROW = auto()
    TEXT = auto()


def arrow_head_points(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    head_len: float = _ARROW_HEAD_LEN,
    head_angle: float = _ARROW_HEAD_ANGLE,
) -> list[tuple[float, float]]:
    """Return the two wing points of an arrow head pointing at ``(x2, y2)``.

    Pure geometry (no Qt) so it can be unit-tested in isolation. The arrow
    points from the tail ``(x1, y1)`` to the tip ``(x2, y2)``; the returned
    points are the two barbs flaring back from the tip.
    """
    angle = math.atan2(y2 - y1, x2 - x1)
    left = (
        x2 - head_len * math.cos(angle - head_angle),
        y2 - head_len * math.sin(angle - head_angle),
    )
    right = (
        x2 - head_len * math.cos(angle + head_angle),
        y2 - head_len * math.sin(angle + head_angle),
    )
    return [left, right]


class RectAnnotation(QGraphicsRectItem):
    """A movable/selectable rectangle with a colored border and no fill."""

    def __init__(self, color: QColor, width: int) -> None:
        super().__init__()
        pen = QPen(color, width)
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        self.setPen(pen)
        self.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)


class ArrowAnnotation(QGraphicsItem):
    """A movable/selectable arrow drawn from a tail point to a tip point.

    Geometry is stored in item-local coordinates; the item is positioned in the
    scene via ``setPos``.
    """

    def __init__(self, color: QColor, width: int) -> None:
        super().__init__()
        self._color = QColor(color)
        self._width = int(width)
        self._tail = QPointF(0, 0)
        self._tip = QPointF(0, 0)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)

    def set_line(self, tail: QPointF, tip: QPointF) -> None:
        self.prepareGeometryChange()
        self._tail = QPointF(tail)
        self._tip = QPointF(tip)
        self.update()

    def _head_len(self) -> float:
        # Scale the head a bit with the pen width so thick arrows look right.
        return _ARROW_HEAD_LEN + self._width * 1.5

    def _wings(self) -> list[QPointF]:
        pts = arrow_head_points(
            self._tail.x(),
            self._tail.y(),
            self._tip.x(),
            self._tip.y(),
            head_len=self._head_len(),
        )
        return [QPointF(px, py) for px, py in pts]

    def boundingRect(self) -> QRectF:
        extra = self._width + self._head_len()
        return QRectF(self._tail, self._tip).normalized().adjusted(
            -extra, -extra, extra, extra
        )

    def shape(self) -> QPainterPath:
        # A thick stroke along the shaft makes the arrow easy to click/select.
        stroker_path = QPainterPath(self._tail)
        stroker_path.lineTo(self._tip)
        pen = QPen()
        pen.setWidthF(max(self._width, 6) + 6)
        stroker = QPainterPathStroker(pen)
        path = stroker.createStroke(stroker_path)
        # Include the head so the tip area is also hittable.
        head = QPolygonF([self._tip, *self._wings()])
        path.addPolygon(head)
        return path

    def paint(self, painter: QPainter, option, widget=None) -> None:  # noqa: ARG002
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(self._color, self._width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawLine(QLineF(self._tail, self._tip))

        # Filled triangular head.
        head = QPolygonF([self._tip, *self._wings()])
        painter.setBrush(QBrush(self._color))
        painter.drawPolygon(head)


class AnnotationView(QGraphicsView):
    """Canvas that hosts the capture plus editable annotations."""

    def __init__(self, base_rgb: np.ndarray, color: QColor, width: int) -> None:
        super().__init__()
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        base = QPixmap.fromImage(imageutil.rgb_to_qimage(base_rgb))
        self._base_item = self._scene.addPixmap(base)
        self._base_item.setZValue(0)
        self._base_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self._scene.setSceneRect(QRectF(base.rect()))

        self._tool = Tool.SELECT
        self._color = QColor(color)
        self._width = int(width)

        # In-progress item while dragging to create a rect/arrow.
        self._draft: QGraphicsItem | None = None
        self._draft_origin = QPointF()

        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)

    # --- public API ------------------------------------------------------
    def set_tool(self, tool: Tool) -> None:
        self._tool = tool
        if tool == Tool.SELECT:
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        else:
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.viewport().setCursor(Qt.CursorShape.CrossCursor)

    def set_color(self, color: QColor) -> None:
        self._color = QColor(color)
        for item in self._scene.selectedItems():
            self._apply_color(item, self._color)

    def set_width(self, width: int) -> None:
        self._width = int(width)
        for item in self._scene.selectedItems():
            self._apply_width(item, self._width)

    def delete_selected(self) -> None:
        for item in self._scene.selectedItems():
            if item is not self._base_item:
                self._scene.removeItem(item)

    def render_to_rgb(self) -> np.ndarray:
        """Flatten the base image plus annotations into an RGB array."""
        self._scene.clearSelection()
        rect = self._base_item.pixmap().rect()
        image = QImage(
            rect.width(), rect.height(), QImage.Format.Format_RGB888
        )
        image.fill(Qt.GlobalColor.white)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        # Render only the scene area covered by the image, at native resolution.
        self._scene.render(painter, QRectF(image.rect()), QRectF(rect))
        painter.end()
        return imageutil.qimage_to_rgb(image)

    # --- helpers ---------------------------------------------------------
    @staticmethod
    def _apply_color(item: QGraphicsItem, color: QColor) -> None:
        if isinstance(item, ArrowAnnotation):
            item._color = QColor(color)
            item.update()
        elif isinstance(item, QGraphicsTextItem):
            item.setDefaultTextColor(color)
        elif hasattr(item, "pen"):
            pen = item.pen()
            pen.setColor(color)
            item.setPen(pen)

    @staticmethod
    def _apply_width(item: QGraphicsItem, width: int) -> None:
        if isinstance(item, ArrowAnnotation):
            item.prepareGeometryChange()
            item._width = int(width)
            item.update()
        elif hasattr(item, "pen"):
            pen = item.pen()
            pen.setWidth(int(width))
            item.setPen(pen)

    # --- interaction -----------------------------------------------------
    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self._tool == Tool.SELECT:
            super().mousePressEvent(event)
            return

        pos = self.mapToScene(event.position().toPoint())

        if self._tool == Tool.RECT:
            item = RectAnnotation(self._color, self._width)
            item.setRect(QRectF(pos, pos))
            self._scene.addItem(item)
            self._draft = item
            self._draft_origin = pos
        elif self._tool == Tool.ARROW:
            item = ArrowAnnotation(self._color, self._width)
            item.setPos(pos)
            item.set_line(QPointF(0, 0), QPointF(0, 0))
            self._scene.addItem(item)
            self._draft = item
            self._draft_origin = pos
        elif self._tool == Tool.TEXT:
            self._add_text(pos)

    def mouseMoveEvent(self, event) -> None:
        if self._draft is None:
            super().mouseMoveEvent(event)
            return

        pos = self.mapToScene(event.position().toPoint())
        if isinstance(self._draft, RectAnnotation):
            self._draft.setRect(QRectF(self._draft_origin, pos).normalized())
        elif isinstance(self._draft, ArrowAnnotation):
            # Geometry is item-local; tail stays at origin.
            self._draft.set_line(QPointF(0, 0), pos - self._draft_origin)

    def mouseReleaseEvent(self, event) -> None:
        if self._draft is None:
            super().mouseReleaseEvent(event)
            return

        # Discard zero-size drafts (a click without a drag).
        discard = False
        if isinstance(self._draft, RectAnnotation):
            r = self._draft.rect()
            discard = r.width() < 3 and r.height() < 3
        elif isinstance(self._draft, ArrowAnnotation):
            line = QLineF(self._draft._tail, self._draft._tip)
            discard = line.length() < 3
        if discard:
            self._scene.removeItem(self._draft)

        self._draft = None
        self.set_tool(Tool.SELECT)

    def _add_text(self, pos: QPointF) -> None:
        item = QGraphicsTextItem()
        item.setPlainText("Texto")
        item.setDefaultTextColor(self._color)
        font = item.font()
        font.setPointSize(max(12, self._width * 6))
        item.setFont(font)
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        item.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        item.setPos(pos)
        self._scene.addItem(item)
        item.setFocus()
        # Select all so the user can type over the placeholder immediately.
        cursor = item.textCursor()
        cursor.select(cursor.SelectionType.Document)
        item.setTextCursor(cursor)
        self.set_tool(Tool.SELECT)

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            # Don't steal Backspace while editing text.
            focus = self._scene.focusItem()
            if isinstance(focus, QGraphicsTextItem):
                super().keyPressEvent(event)
                return
            self.delete_selected()
            return
        if key == Qt.Key.Key_Escape:
            self._scene.clearFocus()
            self.set_tool(Tool.SELECT)
            return
        super().keyPressEvent(event)
