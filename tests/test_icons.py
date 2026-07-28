"""Smoke tests for the painted toolbar icons (offscreen Qt)."""
import os

import pytest


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
    except Exception:  # pragma: no cover - Qt not installed
        pytest.skip("PySide6 not available")
    return QApplication.instance() or QApplication([])


def test_icons_render_non_empty(qapp):
    from PySide6.QtCore import QSize

    from snappr import icons

    factories = [
        icons.select_icon,
        icons.rect_icon,
        icons.oval_icon,
        icons.pixelate_icon,
        icons.arrow_icon,
        icons.text_icon,
        icons.counter_icon,
        icons.trash_icon,
        icons.width_icon,
    ]
    for factory in factories:
        icon = factory()
        assert not icon.isNull()
        pix = icon.pixmap(QSize(18, 18))
        assert not pix.isNull()
        img = pix.toImage()
        has_ink = any(
            img.pixelColor(x, y).alpha() > 0
            for x in range(img.width())
            for y in range(img.height())
        )
        assert has_ink, f"{factory.__name__} produced a fully transparent icon"
