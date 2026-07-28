"""Screen capture primitives built on top of `mss`.

All functions return RGB images as numpy arrays with shape (H, W, 3),
dtype uint8. This is the canonical in-memory format used across the app.
"""
from __future__ import annotations

from dataclasses import dataclass

import mss
import numpy as np


@dataclass(frozen=True)
class Region:
    x: int
    y: int
    width: int
    height: int

    @property
    def is_valid(self) -> bool:
        return self.width > 0 and self.height > 0

    def to_mss(self) -> dict:
        return {
            "left": self.x,
            "top": self.y,
            "width": self.width,
            "height": self.height,
        }


def _shot_to_rgb(shot) -> np.ndarray:
    """Convert an mss screenshot (BGRA) into a contiguous RGB array."""
    bgra = np.frombuffer(shot.raw, dtype=np.uint8)
    bgra = bgra.reshape((shot.height, shot.width, 4))
    # mss raw is BGRA; drop alpha and flip channels to RGB.
    rgb = bgra[:, :, [2, 1, 0]]
    return np.ascontiguousarray(rgb)


def virtual_screen_region() -> Region:
    """Bounding box covering all monitors (the full virtual desktop)."""
    with mss.mss() as sct:
        mon = sct.monitors[0]  # index 0 is the union of all monitors
        return Region(mon["left"], mon["top"], mon["width"], mon["height"])


def grab_region(region: Region) -> np.ndarray:
    with mss.mss() as sct:
        shot = sct.grab(region.to_mss())
        return _shot_to_rgb(shot)


def grab_fullscreen() -> np.ndarray:
    """Grab the entire virtual desktop (all monitors)."""
    return grab_region(virtual_screen_region())


def grab_primary() -> np.ndarray:
    """Grab only the primary monitor."""
    with mss.mss() as sct:
        mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
        shot = sct.grab(mon)
        return _shot_to_rgb(shot)
