"""Helpers to convert images and persist/copy them."""
from __future__ import annotations

import datetime as _dt
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PySide6.QtGui import QImage


def rgb_to_qimage(rgb: np.ndarray) -> QImage:
    """Convert an (H, W, 3) RGB uint8 array into a QImage (copied, owns data)."""
    rgb = np.ascontiguousarray(rgb)
    h, w, _ = rgb.shape
    bytes_per_line = 3 * w
    qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
    return qimg.copy()


def qimage_to_rgb(qimg: QImage) -> np.ndarray:
    """Convert a QImage to an (H, W, 3) RGB uint8 numpy array."""
    qimg = qimg.convertToFormat(QImage.Format.Format_RGB888)
    w, h = qimg.width(), qimg.height()
    ptr = qimg.constBits()
    arr = np.frombuffer(ptr, dtype=np.uint8).reshape((h, qimg.bytesPerLine()))
    arr = arr[:, : w * 3].reshape((h, w, 3))
    return np.ascontiguousarray(arr)


def default_filename() -> str:
    ts = _dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return f"Shottr_{ts}.png"


def save_png(rgb: np.ndarray, out_dir: Path, filename: str | None = None) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / (filename or default_filename())
    rgb_to_qimage(rgb).save(str(path), "PNG")
    return path


def copy_to_clipboard(rgb: np.ndarray) -> bool:
    """Copy image to the clipboard.

    Tries the Qt clipboard first (when a QApplication is running); falls
    back to writing a temp PNG and piping it through `xclip` on X11.
    """
    try:
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is not None:
            app.clipboard().setImage(rgb_to_qimage(rgb))
            return True
    except Exception:
        pass

    if shutil.which("xclip"):
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            save_png(rgb, tmp_path.parent, tmp_path.name)
            with open(tmp_path, "rb") as fh:
                subprocess.run(
                    ["xclip", "-selection", "clipboard", "-t", "image/png"],
                    stdin=fh,
                    check=True,
                )
            return True
        except Exception:
            return False
    return False
