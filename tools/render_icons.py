#!/usr/bin/env python3
"""Render assets/snappr.svg into PNG icons at standard freedesktop sizes.

Used by install.sh to populate the user's hicolor icon theme so the app
icon reliably shows up in desktop menus (some desktops skip themes that
only provide scalable icons without an index.theme/cache).
"""
from __future__ import annotations

import sys
from pathlib import Path

SIZES = (16, 22, 24, 32, 48, 64, 128, 256)


def main() -> int:
    default_root = Path.home() / ".local" / "share" / "icons" / "hicolor"
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else default_root
    svg = Path(__file__).resolve().parent.parent / "assets" / "snappr.svg"

    from PySide6.QtGui import QGuiApplication, QIcon

    app = QGuiApplication(sys.argv[:1])  # noqa: F841 (keep ref alive)
    icon = QIcon(str(svg))
    if icon.isNull():
        print(f"Could not load icon: {svg}", file=sys.stderr)
        return 1

    for size in SIZES:
        out_dir = root / f"{size}x{size}" / "apps"
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / "snappr.png"
        icon.pixmap(size, size).save(str(out), "PNG")
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
