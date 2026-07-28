"""Editable annotation canvas shown in the preview window.

The capture is placed as a non-interactive background pixmap (z=0) inside a
``QGraphicsScene``; each annotation (rectangle, oval, pixelate, counter, arrow,
text) is a ``QGraphicsItem`` stacked on top. Using ``QGraphicsView`` gives us
selection, moving, z-order and flattening (render-to-image) for free.
"""
from __future__ import annotations

import math
from enum import Enum, auto

import cv2
import numpy as np
from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
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
_RESIZE_HANDLE_SIZE = 8.0
_MIN_ANNOTATION_SIZE = 6.0
_DEFAULT_COUNTER_DIAMETER = 36.0
_MIN_COUNTER_DIAMETER = 22.0


class Tool(Enum):
    """Active annotation tool."""

    SELECT = auto()
    RECT = auto()
    OVAL = auto()
    PIXELATE = auto()
    ARROW = auto()
    TEXT = auto()
    COUNTER = auto()


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


class ResizableBoxAnnotation(QGraphicsRectItem):
    """Base item with eight resize handles around a rectangular geometry."""

    _HANDLE_CURSORS = {
        "top_left": Qt.CursorShape.SizeFDiagCursor,
        "top": Qt.CursorShape.SizeVerCursor,
        "top_right": Qt.CursorShape.SizeBDiagCursor,
        "right": Qt.CursorShape.SizeHorCursor,
        "bottom_right": Qt.CursorShape.SizeFDiagCursor,
        "bottom": Qt.CursorShape.SizeVerCursor,
        "bottom_left": Qt.CursorShape.SizeBDiagCursor,
        "left": Qt.CursorShape.SizeHorCursor,
    }

    def __init__(self, pen: QPen | None = None) -> None:
        super().__init__()
        self.setPen(pen or QPen(Qt.PenStyle.NoPen))
        self.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self._active_handle: str | None = None

    def boundingRect(self) -> QRectF:
        margin = max(
            _RESIZE_HANDLE_SIZE / 2.0 + 1.0,
            self.pen().widthF() / 2.0 + 1.0,
        )
        return self.rect().normalized().adjusted(-margin, -margin, margin, margin)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.addRect(self.rect().normalized())
        if self.isSelected():
            for handle_rect in self._handle_rects().values():
                path.addRect(handle_rect)
        return path

    def _handle_rects(self) -> dict[str, QRectF]:
        rect = self.rect().normalized()
        half = _RESIZE_HANDLE_SIZE / 2.0
        points = {
            "top_left": rect.topLeft(),
            "top": QPointF(rect.center().x(), rect.top()),
            "top_right": rect.topRight(),
            "right": QPointF(rect.right(), rect.center().y()),
            "bottom_right": rect.bottomRight(),
            "bottom": QPointF(rect.center().x(), rect.bottom()),
            "bottom_left": rect.bottomLeft(),
            "left": QPointF(rect.left(), rect.center().y()),
        }
        return {
            name: QRectF(
                point.x() - half,
                point.y() - half,
                _RESIZE_HANDLE_SIZE,
                _RESIZE_HANDLE_SIZE,
            )
            for name, point in points.items()
        }

    def _handle_at(self, pos: QPointF) -> str | None:
        if not self.isSelected():
            return None
        for name, rect in self._handle_rects().items():
            if rect.contains(pos):
                return name
        return None

    def _resize_from_handle(self, handle: str, pos: QPointF) -> None:
        rect = self.rect().normalized()
        if handle in {"top_left", "left", "bottom_left"}:
            rect.setLeft(min(pos.x(), rect.right() - _MIN_ANNOTATION_SIZE))
        if handle in {"top_right", "right", "bottom_right"}:
            rect.setRight(max(pos.x(), rect.left() + _MIN_ANNOTATION_SIZE))
        if handle in {"top_left", "top", "top_right"}:
            rect.setTop(min(pos.y(), rect.bottom() - _MIN_ANNOTATION_SIZE))
        if handle in {"bottom_left", "bottom", "bottom_right"}:
            rect.setBottom(max(pos.y(), rect.top() + _MIN_ANNOTATION_SIZE))
        self.setRect(rect)

    def _paint_content(self, painter: QPainter) -> None:
        painter.setPen(self.pen())
        painter.setBrush(self.brush())
        painter.drawRect(self.rect())

    def paint(self, painter: QPainter, option, widget=None) -> None:  # noqa: ARG002
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self._paint_content(painter)
        if not self.isSelected():
            return

        painter.save()
        selection_pen = QPen(QColor("#1683F3"), 1, Qt.PenStyle.DashLine)
        selection_pen.setCosmetic(True)
        painter.setPen(selection_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self.rect())

        handle_pen = QPen(QColor("#1683F3"), 1)
        handle_pen.setCosmetic(True)
        painter.setPen(handle_pen)
        painter.setBrush(QColor("#FFFFFF"))
        for handle_rect in self._handle_rects().values():
            painter.drawRect(handle_rect)
        painter.restore()

    def hoverMoveEvent(self, event) -> None:
        handle = self._handle_at(event.pos())
        if handle is None:
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        else:
            self.setCursor(self._HANDLE_CURSORS[handle])
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        self.unsetCursor()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event) -> None:
        handle = self._handle_at(event.pos())
        if handle is not None and event.button() == Qt.MouseButton.LeftButton:
            self._active_handle = handle
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._active_handle is not None:
            self._resize_from_handle(self._active_handle, event.pos())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._active_handle is not None:
            self._resize_from_handle(self._active_handle, event.pos())
            self._active_handle = None
            event.accept()
            return
        super().mouseReleaseEvent(event)


class RectAnnotation(ResizableBoxAnnotation):
    """A movable/selectable/resizable rectangle with no fill."""

    def __init__(self, color: QColor, width: int) -> None:
        pen = QPen(color, width)
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        super().__init__(pen)


class OvalAnnotation(ResizableBoxAnnotation):
    """A movable/selectable/resizable oval with no fill."""

    def __init__(self, color: QColor, width: int) -> None:
        pen = QPen(color, width)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        super().__init__(pen)

    def _paint_content(self, painter: QPainter) -> None:
        painter.setPen(self.pen())
        painter.setBrush(self.brush())
        painter.drawEllipse(self.rect())


def pixelate_rgb(rgb: np.ndarray, block_size: int = 12) -> np.ndarray:
    """Return a pixelated copy of an RGB image using averaged color blocks."""
    source = np.ascontiguousarray(rgb)
    height, width = source.shape[:2]
    block_size = max(2, int(block_size))
    small_size = (
        max(1, (width + block_size - 1) // block_size),
        max(1, (height + block_size - 1) // block_size),
    )
    reduced = cv2.resize(source, small_size, interpolation=cv2.INTER_AREA)
    return cv2.resize(reduced, (width, height), interpolation=cv2.INTER_NEAREST)


class PixelateAnnotation(ResizableBoxAnnotation):
    """A movable rectangular window onto a pixelated copy of the capture.

    Its source follows the item's scene position. Moving it therefore pixelates
    the new location instead of carrying pixels from where it was first created.
    """

    def __init__(self, pixelated_base: QPixmap) -> None:
        super().__init__()
        self._pixelated_base = pixelated_base

    def _paint_content(self, painter: QPainter) -> None:
        target = self.rect()
        source = self.mapRectToScene(target)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.drawPixmap(target, self._pixelated_base, source)


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


class CounterAnnotation(QGraphicsItem):
    """A movable/selectable/resizable numbered circular marker."""

    _HANDLE_CURSORS = {
        "top_left": Qt.CursorShape.SizeFDiagCursor,
        "top_right": Qt.CursorShape.SizeBDiagCursor,
        "bottom_right": Qt.CursorShape.SizeFDiagCursor,
        "bottom_left": Qt.CursorShape.SizeBDiagCursor,
    }

    def __init__(self, number: int, color: QColor) -> None:
        super().__init__()
        self._number = int(number)
        self._color = QColor(color)
        self._diameter = _DEFAULT_COUNTER_DIAMETER
        self._active_handle: str | None = None
        self._resize_anchor: QPointF | None = None
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)

    @property
    def number(self) -> int:
        return self._number

    @property
    def diameter(self) -> float:
        return self._diameter

    def set_color(self, color: QColor) -> None:
        self._color = QColor(color)
        self.update()

    def _circle_rect(self) -> QRectF:
        half = self._diameter / 2.0
        return QRectF(-half, -half, self._diameter, self._diameter)

    def boundingRect(self) -> QRectF:
        margin = _RESIZE_HANDLE_SIZE / 2.0 + 1.0
        return self._circle_rect().adjusted(-margin, -margin, margin, margin)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.addEllipse(self._circle_rect())
        if self.isSelected():
            for handle_rect in self._handle_rects().values():
                path.addRect(handle_rect)
        return path

    def _handle_rects(self) -> dict[str, QRectF]:
        circle = self._circle_rect()
        half_handle = _RESIZE_HANDLE_SIZE / 2.0
        points = {
            "top_left": circle.topLeft(),
            "top_right": circle.topRight(),
            "bottom_right": circle.bottomRight(),
            "bottom_left": circle.bottomLeft(),
        }
        return {
            name: QRectF(
                point.x() - half_handle,
                point.y() - half_handle,
                _RESIZE_HANDLE_SIZE,
                _RESIZE_HANDLE_SIZE,
            )
            for name, point in points.items()
        }

    def _handle_at(self, pos: QPointF) -> str | None:
        if not self.isSelected():
            return None
        for name, rect in self._handle_rects().items():
            if rect.contains(pos):
                return name
        return None

    def _opposite_corner(self, handle: str) -> QPointF:
        circle = self._circle_rect()
        return {
            "top_left": circle.bottomRight(),
            "top_right": circle.bottomLeft(),
            "bottom_right": circle.topLeft(),
            "bottom_left": circle.topRight(),
        }[handle]

    def _resize_from_handle(self, handle: str, scene_pos: QPointF) -> None:
        if self._resize_anchor is None:
            return
        anchor = self._resize_anchor
        diameter = max(
            _MIN_COUNTER_DIAMETER,
            abs(scene_pos.x() - anchor.x()),
            abs(scene_pos.y() - anchor.y()),
        )
        directions = {
            "top_left": (-1, -1),
            "top_right": (1, -1),
            "bottom_right": (1, 1),
            "bottom_left": (-1, 1),
        }
        horizontal, vertical = directions[handle]
        center = QPointF(
            anchor.x() + horizontal * diameter / 2.0,
            anchor.y() + vertical * diameter / 2.0,
        )
        self.prepareGeometryChange()
        self._diameter = diameter
        self.setPos(center)
        self.update()

    def paint(self, painter: QPainter, option, widget=None) -> None:  # noqa: ARG002
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        circle = self._circle_rect()

        border = QPen(self._color.darker(125), max(1.5, self._diameter * 0.04))
        painter.setPen(border)
        painter.setBrush(self._color)
        painter.drawEllipse(circle)

        # Keep the number legible for both light and dark annotation colors.
        luminance = (
            self._color.red() * 299
            + self._color.green() * 587
            + self._color.blue() * 114
        ) / 1000
        painter.setPen(QColor("#111111") if luminance > 175 else QColor("#FFFFFF"))
        font = QFont()
        font.setBold(True)
        digits = len(str(self._number))
        scale = 0.50 if digits <= 2 else 0.39 if digits == 3 else 0.31
        font.setPixelSize(max(8, int(self._diameter * scale)))
        painter.setFont(font)
        painter.drawText(circle, Qt.AlignmentFlag.AlignCenter, str(self._number))

        if self.isSelected():
            painter.save()
            selection_pen = QPen(QColor("#1683F3"), 1, Qt.PenStyle.DashLine)
            selection_pen.setCosmetic(True)
            painter.setPen(selection_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(circle.adjusted(-2, -2, 2, 2))

            handle_pen = QPen(QColor("#1683F3"), 1)
            handle_pen.setCosmetic(True)
            painter.setPen(handle_pen)
            painter.setBrush(QColor("#FFFFFF"))
            for handle_rect in self._handle_rects().values():
                painter.drawRect(handle_rect)
            painter.restore()

    def hoverMoveEvent(self, event) -> None:
        handle = self._handle_at(event.pos())
        if handle is None:
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        else:
            self.setCursor(self._HANDLE_CURSORS[handle])
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        self.unsetCursor()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event) -> None:
        handle = self._handle_at(event.pos())
        if handle is not None and event.button() == Qt.MouseButton.LeftButton:
            self._active_handle = handle
            self._resize_anchor = self.mapToScene(self._opposite_corner(handle))
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._active_handle is not None:
            self._resize_from_handle(self._active_handle, event.scenePos())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._active_handle is not None:
            self._resize_from_handle(self._active_handle, event.scenePos())
            self._active_handle = None
            self._resize_anchor = None
            event.accept()
            return
        super().mouseReleaseEvent(event)


class AnnotationView(QGraphicsView):
    """Canvas that hosts the capture plus editable annotations."""

    def __init__(self, base_rgb: np.ndarray, color: QColor, width: int) -> None:
        super().__init__()
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        self._base_rgb = np.ascontiguousarray(base_rgb)
        base = QPixmap.fromImage(imageutil.rgb_to_qimage(self._base_rgb))
        self._base_item = self._scene.addPixmap(base)
        self._base_item.setZValue(0)
        self._base_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self._scene.setSceneRect(QRectF(base.rect()))
        # Built lazily because scrolling captures can be very tall and most
        # preview sessions never use the pixelate tool.
        self._pixelated_base: QPixmap | None = None

        self._tool = Tool.SELECT
        self._color = QColor(color)
        self._width = int(width)
        self._next_counter = 1

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

    def _get_pixelated_base(self) -> QPixmap:
        if self._pixelated_base is None:
            self._pixelated_base = QPixmap.fromImage(
                imageutil.rgb_to_qimage(pixelate_rgb(self._base_rgb))
            )
        return self._pixelated_base

    def render_to_rgb(self) -> np.ndarray:
        """Flatten the base image plus annotations into an RGB array."""
        selected_items = self._scene.selectedItems()
        self._scene.clearSelection()
        rect = self._base_item.pixmap().rect()
        image = QImage(
            rect.width(), rect.height(), QImage.Format.Format_RGB888
        )
        image.fill(Qt.GlobalColor.white)
        painter = QPainter(image)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            # Render only the scene area covered by the image, at native resolution.
            self._scene.render(painter, QRectF(image.rect()), QRectF(rect))
        finally:
            painter.end()
            for item in selected_items:
                item.setSelected(True)
        return imageutil.qimage_to_rgb(image)

    # --- helpers ---------------------------------------------------------
    @staticmethod
    def _apply_color(item: QGraphicsItem, color: QColor) -> None:
        if isinstance(item, PixelateAnnotation):
            return
        if isinstance(item, CounterAnnotation):
            item.set_color(color)
        elif isinstance(item, ArrowAnnotation):
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
        if isinstance(item, (PixelateAnnotation, CounterAnnotation)):
            return
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
        elif self._tool == Tool.OVAL:
            item = OvalAnnotation(self._color, self._width)
            item.setRect(QRectF(pos, pos))
            self._scene.addItem(item)
            self._draft = item
            self._draft_origin = pos
        elif self._tool == Tool.PIXELATE:
            item = PixelateAnnotation(self._get_pixelated_base())
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
        elif self._tool == Tool.COUNTER:
            item = CounterAnnotation(self._next_counter, self._color)
            item.setPos(pos)
            self._scene.addItem(item)
            self._next_counter += 1
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._draft is None:
            super().mouseMoveEvent(event)
            return

        pos = self.mapToScene(event.position().toPoint())
        if isinstance(
            self._draft, (RectAnnotation, OvalAnnotation, PixelateAnnotation)
        ):
            self._draft.setRect(QRectF(self._draft_origin, pos).normalized())
        elif isinstance(self._draft, ArrowAnnotation):
            # Geometry is item-local; tail stays at origin.
            self._draft.set_line(QPointF(0, 0), pos - self._draft_origin)

    def mouseReleaseEvent(self, event) -> None:
        if self._tool == Tool.COUNTER and self._draft is None:
            event.accept()
            return
        if self._draft is None:
            super().mouseReleaseEvent(event)
            return

        # Discard zero-size drafts (a click without a drag).
        discard = False
        if isinstance(
            self._draft, (RectAnnotation, OvalAnnotation, PixelateAnnotation)
        ):
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
