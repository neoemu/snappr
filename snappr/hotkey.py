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


_MODIFIERS = {
    "ctrl": "<ctrl>",
    "control": "<ctrl>",
    "shift": "<shift>",
    "alt": "<alt>",
    "meta": "<cmd>",
    "super": "<cmd>",
}
_DISPLAY_MODIFIERS = {
    "<ctrl>": "Ctrl",
    "<shift>": "Shift",
    "<alt>": "Alt",
    "<cmd>": "Meta",
}
_SPECIAL_KEYS = {
    "space": "<space>",
    "tab": "<tab>",
    "enter": "<enter>",
    "return": "<enter>",
    "esc": "<esc>",
    "escape": "<esc>",
    "backspace": "<backspace>",
    "delete": "<delete>",
    "insert": "<insert>",
    "home": "<home>",
    "end": "<end>",
    "pgup": "<page_up>",
    "pageup": "<page_up>",
    "pgdown": "<page_down>",
    "pagedown": "<page_down>",
    "print": "<print_screen>",
    "printscreen": "<print_screen>",
    "pause": "<pause>",
    "up": "<up>",
    "down": "<down>",
    "left": "<left>",
    "right": "<right>",
}


def hotkey_to_pynput(value: str) -> str:
    """Convert a Qt-style shortcut such as ``Ctrl+Shift+A`` to pynput syntax."""
    value = value.strip()
    if not value:
        raise ValueError("Hotkey cannot be empty")
    if value.startswith("<"):
        normalized = value.lower()
        _validate_pynput_hotkey(normalized)
        return normalized

    parts = [part.strip() for part in value.split("+") if part.strip()]
    if not parts:
        raise ValueError("Hotkey cannot be empty")

    converted: list[str] = []
    for part in parts[:-1]:
        modifier = _MODIFIERS.get(part.casefold())
        if modifier is None:
            raise ValueError(f"Unsupported modifier: {part}")
        converted.append(modifier)

    key = parts[-1]
    key_lower = key.casefold()
    if len(key) == 1:
        converted.append(key_lower)
    elif key_lower in _SPECIAL_KEYS:
        converted.append(_SPECIAL_KEYS[key_lower])
    elif key_lower.startswith("f") and key_lower[1:].isdigit():
        number = int(key_lower[1:])
        if not 1 <= number <= 20:
            raise ValueError(f"Unsupported function key: {key}")
        converted.append(f"<f{number}>")
    else:
        raise ValueError(f"Unsupported key: {key}")
    normalized = "+".join(converted)
    _validate_pynput_hotkey(normalized)
    return normalized


def _validate_pynput_hotkey(value: str) -> None:
    if keyboard is None:
        return
    try:
        keyboard.HotKey.parse(value)
    except (KeyError, ValueError) as exc:
        raise ValueError(f"Unsupported hotkey: {value}") from exc


def hotkey_to_display(value: str) -> str:
    """Convert persisted pynput syntax to a QKeySequence-friendly string."""
    parts = [part.strip().lower() for part in value.split("+") if part.strip()]
    displayed: list[str] = []
    reverse_special = {v: k.title() for k, v in _SPECIAL_KEYS.items()}
    reverse_special["<enter>"] = "Enter"
    reverse_special["<esc>"] = "Esc"
    reverse_special["<page_up>"] = "PgUp"
    reverse_special["<page_down>"] = "PgDown"
    reverse_special["<print_screen>"] = "Print"
    for part in parts:
        if part in _DISPLAY_MODIFIERS:
            displayed.append(_DISPLAY_MODIFIERS[part])
        elif part in reverse_special:
            displayed.append(reverse_special[part])
        elif part.startswith("<f") and part.endswith(">"):
            displayed.append(part[1:-1].upper())
        elif len(part) == 1:
            displayed.append(part.upper())
        else:
            displayed.append(part)
    return "+".join(displayed)


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

    def restart(self, bindings: dict[str, Callable[[], None]]) -> bool:
        """Replace all bindings and start a fresh listener."""
        self.stop()
        self._bindings = bindings
        return self.start()
