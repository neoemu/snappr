"""Global hotkey support via pynput.

pynput runs its listener in a background thread. Callbacks therefore must be
thread-safe with respect to Qt. The recommended pattern is to have callbacks
emit a Qt signal (queued connections marshal the call to the GUI thread).
"""
from __future__ import annotations

from typing import Callable

try:
    from pynput import keyboard
except Exception:  # pragma: no cover - import guarded for headless envs
    keyboard = None  # type: ignore


class HotkeyManager:
    """Registers a set of global hotkeys mapped to callables."""

    def __init__(self, bindings: dict[str, Callable[[], None]]) -> None:
        self._bindings = bindings
        self._listener = None

    @property
    def available(self) -> bool:
        return keyboard is not None

    def start(self) -> bool:
        if keyboard is None or not self._bindings:
            return False
        try:
            self._listener = keyboard.GlobalHotKeys(self._bindings)
            self._listener.start()
            return True
        except Exception:
            self._listener = None
            return False

    def stop(self) -> None:
        if self._listener is not None:
            try:
                self._listener.stop()
            finally:
                self._listener = None
