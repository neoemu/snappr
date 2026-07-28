"""Application controller: wires tray, hotkeys and capture flows together."""
from __future__ import annotations

import signal
import sys

import numpy as np
from PySide6.QtCore import QObject, QTimer, Signal, Slot
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from . import capture
from .config import Config
from .hotkey import HotkeyManager
from .overlay import RegionSelector
from .preview import PreviewWindow
from .scroll_capture import ScrollCaptureSession
from .settings import SettingsDialog
from .tray import build_tray


class SnapprApp(QObject):
    """Owns app-wide state and the capture flows.

    The ``*_requested`` signals exist so global-hotkey callbacks (which fire on
    pynput's background thread) can safely hop onto the Qt GUI thread via
    queued signal/slot connections.
    """

    region_requested = Signal()
    fullscreen_requested = Signal()
    scroll_requested = Signal()

    def __init__(self, qapp: QApplication) -> None:
        super().__init__()
        self.qapp = qapp
        self.config = Config.load()

        # Keep strong refs so windows/sessions aren't garbage-collected.
        self._windows: list = []
        self._selector: RegionSelector | None = None
        self._session: ScrollCaptureSession | None = None

        # Marshal hotkey-thread signals onto the GUI thread.
        self.region_requested.connect(self.start_region_capture)
        self.fullscreen_requested.connect(self.start_fullscreen_capture)
        self.scroll_requested.connect(self.start_scroll_capture)

        self.tray = build_tray(self)
        self.tray.show()

        self.hotkeys = HotkeyManager(self._hotkey_bindings())
        self.qapp.aboutToQuit.connect(self.hotkeys.stop)
        if not self.hotkeys.start():
            self._show_hotkey_warning()

    # --- capture flows ---------------------------------------------------
    @Slot()
    def start_fullscreen_capture(self) -> None:
        # Small delay lets the tray menu close before grabbing.
        QTimer.singleShot(250, self._do_fullscreen)

    def _do_fullscreen(self) -> None:
        rgb = capture.grab_fullscreen()
        self._show_preview(rgb)

    @Slot()
    def start_region_capture(self) -> None:
        self._selector = RegionSelector()
        self._selector.selected.connect(self._on_region_selected)
        self._selector.show()
        self._selector.raise_()
        self._selector.activateWindow()

    def _on_region_selected(self, region) -> None:
        self._selector = None
        if region is None:
            return
        QTimer.singleShot(80, lambda: self._show_preview(capture.grab_region(region)))

    @Slot()
    def start_scroll_capture(self) -> None:
        self._selector = RegionSelector()
        self._selector.selected.connect(self._on_scroll_region_selected)
        self._selector.show()
        self._selector.raise_()
        self._selector.activateWindow()

    def _on_scroll_region_selected(self, region) -> None:
        self._selector = None
        if region is None:
            return
        # Delay so the selection overlay is fully gone from the screen before
        # the first frame is grabbed; otherwise its blue border gets baked
        # into the stitched image.
        QTimer.singleShot(250, lambda: self._begin_scroll_session(region))

    def _begin_scroll_session(self, region) -> None:
        self._session = ScrollCaptureSession(region)
        self._session.finished.connect(self._on_scroll_finished)
        self._session.cancelled.connect(self._on_scroll_cancelled)
        self._session.start()

    def _on_scroll_finished(self, rgb: np.ndarray) -> None:
        self._session = None
        self._show_preview(rgb)

    def _on_scroll_cancelled(self) -> None:
        self._session = None

    # --- helpers ---------------------------------------------------------
    def _show_preview(self, rgb: np.ndarray) -> None:
        win = PreviewWindow(rgb, self.config)
        win.show()
        win.raise_()
        win.activateWindow()
        self._windows.append(win)

    def _hotkey_bindings(self) -> dict:
        return {
            self.config["hotkey_region"]: self.region_requested.emit,
            self.config["hotkey_fullscreen"]: self.fullscreen_requested.emit,
            self.config["hotkey_scroll"]: self.scroll_requested.emit,
        }

    def _show_hotkey_warning(self) -> None:
        self.tray.showMessage(
            "Snappr",
            "Global hotkeys unavailable; use the tray menu.",
            QSystemTrayIcon.MessageIcon.Information,
            4000,
        )

    @Slot()
    def show_settings(self) -> None:
        # Avoid firing a capture while the user records a shortcut.
        self.hotkeys.stop()
        dialog = SettingsDialog(self.config)
        dialog.exec()
        if not self.hotkeys.restart(self._hotkey_bindings()):
            self._show_hotkey_warning()

    @Slot()
    def quit(self) -> None:
        self.hotkeys.stop()
        self.qapp.quit()


def main() -> int:
    qapp = QApplication(sys.argv)
    qapp.setApplicationName("Snappr")
    # Keep running in the tray even when no window is open.
    qapp.setQuitOnLastWindowClosed(False)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("Warning: system tray unavailable; the app may not appear.",
              file=sys.stderr)

    _app = SnapprApp(qapp)  # noqa: F841 (keep ref alive)

    # Python only dispatches Unix signals while it is executing Python
    # bytecode. A short Qt timer gives it regular opportunities to process
    # Ctrl+C instead of leaving KeyboardInterrupt pending until the next UI
    # callback (for example, clicking the tray's Quit action).
    signal.signal(signal.SIGINT, lambda _signum, _frame: qapp.quit())
    signal.signal(signal.SIGTERM, lambda _signum, _frame: qapp.quit())
    signal_timer = QTimer(qapp)
    signal_timer.timeout.connect(lambda: None)
    signal_timer.start(200)

    return qapp.exec()


if __name__ == "__main__":
    raise SystemExit(main())
