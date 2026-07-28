"""Persistent configuration stored as JSON in ~/.config/snappr/."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "snappr"
CONFIG_PATH = CONFIG_DIR / "config.json"

DEFAULTS: dict[str, Any] = {
    # Where PNGs are saved by default.
    "output_dir": str(Path.home() / "Pictures" / "Screenshots"),
    # Skip the file dialog and save immediately to output_dir.
    "save_directly": False,
    # Global hotkey to start a region capture (pynput format).
    "hotkey_region": "<ctrl>+<shift>+a",
    # Global hotkey to start a scrolling capture.
    "hotkey_scroll": "<ctrl>+<shift>+s",
    # Global hotkey to grab the full screen.
    "hotkey_fullscreen": "<ctrl>+<shift>+f",
    # Copy result to clipboard automatically after a capture.
    "auto_copy": True,
    # Default annotation pen color (hex) and width (px).
    "annot_color": "#FF3B30",
    "annot_width": 3,
}


class Config:
    def __init__(self, data: dict[str, Any] | None = None) -> None:
        self._data = {**DEFAULTS, **(data or {})}

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    @property
    def output_dir(self) -> Path:
        path = Path(self._data["output_dir"]).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    @classmethod
    def load(cls) -> "Config":
        if CONFIG_PATH.exists():
            try:
                data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                return cls(data)
            except (json.JSONDecodeError, OSError):
                pass
        cfg = cls()
        cfg.save()
        return cfg
