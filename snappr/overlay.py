"""Fullscreen translucent overlay used to select a screen region.

Usage::

    rect = RegionSelector.select()  # blocks until user picks or cancels
    if rect is not None:
        ...  # rect is a snappr.capture.Region in global screen coords

The selector spans the whole virtual desktop. The user drags a rectangle;
releasing the mouse confirms, pressing Escape cancels.
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QKeyEvent, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .capture import Region


class RegionSelector(QWidget):
    """Translucent fullscreen widget that emits a selected rectangle."""

    selected = Signal(object)  # emits Region or None

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)

        # Cover the entire virtual desktop (all monitors).
        geo = QGuiApplication.primaryScreen().virtualGeometry()
        self.setGeometry(geo)
        self._origin_offset = geo.topLeft()

        self._start: QPoint | None = None
        self._end: QPoint | None = None
        self._result: Region | None = None

    # --- interaction -----------------------------------------------------
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._start = event.position().toPoint()
            self._end = self._start
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._start is not None:
            self._end = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._start is not None:
            self._end = event.position().toPoint()
            self._finish()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self._result = None
            self.close()
            self.selected.emit(None)

    # --- painting --------------------------------------------------------
    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 110))

        if self._start is not None and self._end is not None:
            sel = QRect(self._start, self._end).normalized()
            # Punch a clear hole where the selection is.
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(sel, Qt.GlobalColor.transparent)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

            pen = QPen(QColor(0, 174, 255), 2)
            painter.setPen(pen)
            painter.drawRect(sel)

            label = f"{sel.width()} x {sel.height()}"
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(sel.topLeft() + QPoint(4, -6), label)

    # --- helpers ---------------------------------------------------------
    def _finish(self) -> None:
        rect = QRect(self._start, self._end).normalized()
        self.close()
        if rect.width() < 3 or rect.height() < 3:
            self._result = None
            self.selected.emit(None)
            return
        # Translate widget-local coords back to absolute screen coords.
        gx = rect.x() + self._origin_offset.x()
        gy = rect.y() + self._origin_offset.y()
        self._result = Region(gx, gy, rect.width(), rect.height())
        self.selected.emit(self._result)
