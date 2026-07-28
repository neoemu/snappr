"""Automatic scrolling-capture session.

Flow:
1. Caller provides a fixed :class:`Region`.
2. The first frame is captured before any synthetic scroll.
3. The mouse cursor is moved to the center of the region and the app sends
   small downward wheel steps automatically.
4. After each wheel step, the region is captured and fed to
   :class:`ScrollStitcher`.
5. Capture finishes when repeated wheel steps no longer change the view, or
   when the user presses Enter/Space/Ctrl+Enter. Escape cancels.

There is intentionally no on-screen control bar: anything drawn on top of the
selected region becomes part of the screenshot and destabilizes stitching.
"""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QObject, QTimer, Signal

from . import capture
from .capture import Region
from .stitch import ScrollStitcher

try:
    from pynput import keyboard as pynput_keyboard
    from pynput import mouse as pynput_mouse
except Exception:  # pragma: no cover - import guarded for headless envs
    pynput_keyboard = None  # type: ignore
    pynput_mouse = None  # type: ignore


class ScrollCaptureSession(QObject):
    """Drives an automatic scrolling capture for a fixed region."""

    finished = Signal(object)   # emits np.ndarray (RGB) result
    cancelled = Signal()
    finish_requested = Signal()
    cancel_requested = Signal()

    def __init__(
        self,
        region: Region,
        scroll_units: int = 1,
        settle_ms: int = 180,
        stable_limit: int = 4,
        max_steps: int = 500,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.region = region
        self.scroll_units = max(1, scroll_units)
        self.settle_ms = max(50, settle_ms)
        self.stable_limit = max(2, stable_limit)
        self.max_steps = max(1, max_steps)

        self.stitcher = ScrollStitcher()
        self.finish_requested.connect(self._finish)
        self.cancel_requested.connect(self._cancel)

        self._key_listener = None
        self._mouse = self._create_mouse_controller()
        self._original_mouse_pos = None
        self._previous_frame: np.ndarray | None = None
        self._stable_count = 0
        self._steps = 0
        self._done = False

    def start(self) -> None:
        self._capture_initial_frame()
        self._start_key_listener()
        self._move_mouse_to_region_center()
        QTimer.singleShot(self.settle_ms, self._scroll_once)

    # --- capture loop ----------------------------------------------------
    def _create_mouse_controller(self):
        if pynput_mouse is None:
            return None
        try:
            return pynput_mouse.Controller()
        except Exception:
            return None

    def _capture_initial_frame(self) -> None:
        frame = capture.grab_region(self.region)
        self.stitcher.add_frame(frame)
        self._previous_frame = frame

    def _scroll_once(self) -> None:
        if self._done:
            return
        if self._steps >= self.max_steps:
            self._finish()
            return
        if self._mouse is None:
            self._finish()
            return

        self._mouse.scroll(0, -self.scroll_units)
        self._steps += 1
        QTimer.singleShot(self.settle_ms, self._capture_after_scroll)

    def _capture_after_scroll(self) -> None:
        if self._done:
            return

        try:
            frame = capture.grab_region(self.region)
        except Exception:
            QTimer.singleShot(self.settle_ms, self._scroll_once)
            return

        if self._previous_frame is not None and self._frames_are_similar(
            self._previous_frame,
            frame,
        ):
            self._stable_count += 1
        else:
            self._stable_count = 0

        self.stitcher.add_frame(frame)
        self._previous_frame = frame

        if self._stable_count >= self.stable_limit:
            self._finish()
            return

        QTimer.singleShot(self.settle_ms, self._scroll_once)

    def _frames_are_similar(self, a: np.ndarray, b: np.ndarray) -> bool:
        if a.shape != b.shape:
            return False
        # Use a sampled grid to keep this cheap for large screenshots.
        step_y = max(1, a.shape[0] // 120)
        step_x = max(1, a.shape[1] // 120)
        a_sample = a[::step_y, ::step_x].astype(np.int16)
        b_sample = b[::step_y, ::step_x].astype(np.int16)
        mean_abs_delta = np.abs(a_sample - b_sample).mean()
        return bool(mean_abs_delta < 1.0)

    # --- input / cleanup -------------------------------------------------
    def _move_mouse_to_region_center(self) -> None:
        if self._mouse is None:
            return
        try:
            self._original_mouse_pos = self._mouse.position
            self._mouse.position = (
                self.region.x + max(1, self.region.width // 2),
                self.region.y + max(1, self.region.height // 2),
            )
        except Exception:
            self._original_mouse_pos = None

    def _restore_mouse_position(self) -> None:
        if self._mouse is None or self._original_mouse_pos is None:
            return
        try:
            self._mouse.position = self._original_mouse_pos
        except Exception:
            pass

    def _start_key_listener(self) -> None:
        if pynput_keyboard is None:
            return
        try:
            self._key_listener = pynput_keyboard.GlobalHotKeys(
                {
                    "<ctrl>+<enter>": self.finish_requested.emit,
                    "<enter>": self.finish_requested.emit,
                    "<space>": self.finish_requested.emit,
                    "<esc>": self.cancel_requested.emit,
                }
            )
            self._key_listener.start()
        except Exception:
            self._key_listener = None

    def _stop_key_listener(self) -> None:
        if self._key_listener is None:
            return
        try:
            self._key_listener.stop()
        finally:
            self._key_listener = None

    def _finish(self) -> None:
        if self._done:
            return
        self._done = True
        self._stop_key_listener()
        self._restore_mouse_position()
        result = self.stitcher.result()
        if result is None:
            self.cancelled.emit()
        else:
            self.finished.emit(np.ascontiguousarray(result))

    def _cancel(self) -> None:
        if self._done:
            return
        self._done = True
        self._stop_key_listener()
        self._restore_mouse_position()
        self.cancelled.emit()
