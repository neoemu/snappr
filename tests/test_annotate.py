"""Tests for the annotation layer.

The geometry test is pure (no Qt). The GUI smoke test exercises the real
``AnnotationView`` flattening path under the Qt ``offscreen`` platform, and is
skipped gracefully if a Qt runtime isn't available.
"""
import math
import os

import numpy as np
import pytest

from snappr.annotate import arrow_head_points


def test_arrow_head_points_for_horizontal_arrow():
    # Arrow pointing straight to the right, tip at (100, 0).
    head_len = 18.0
    angle = math.radians(28.0)
    left, right = arrow_head_points(0, 0, 100, 0, head_len=head_len, head_angle=angle)

    # Both barbs sit behind the tip (smaller x) and are vertically mirrored.
    assert left[0] < 100 and right[0] < 100
    assert left[1] == pytest.approx(-right[1])
    # Each barb is exactly head_len away from the tip.
    for px, py in (left, right):
        dist = math.hypot(100 - px, 0 - py)
        assert dist == pytest.approx(head_len)


def test_arrow_head_points_follow_direction():
    # Arrow pointing down: barbs should be above the tip (smaller y).
    left, right = arrow_head_points(0, 0, 0, 100)
    assert left[1] < 100 and right[1] < 100


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
    except Exception:  # pragma: no cover - Qt not installed
        pytest.skip("PySide6 not available")
    app = QApplication.instance() or QApplication([])
    return app


def test_render_to_rgb_includes_annotations(qapp):
    from PySide6.QtCore import QPointF, QRectF
    from PySide6.QtGui import QColor

    from snappr.annotate import AnnotationView, ArrowAnnotation, RectAnnotation

    base = np.zeros((120, 160, 3), dtype=np.uint8)  # all black
    view = AnnotationView(base, QColor("#FF0000"), 4)

    rect = RectAnnotation(QColor("#FF0000"), 4)
    rect.setRect(QRectF(20, 20, 60, 40))
    view._scene.addItem(rect)

    arrow = ArrowAnnotation(QColor("#00FF00"), 4)
    arrow.setPos(QPointF(90, 20))
    arrow.set_line(QPointF(0, 0), QPointF(40, 50))
    view._scene.addItem(arrow)

    out = view.render_to_rgb()

    assert out.shape == (120, 160, 3)
    assert out.dtype == np.uint8
    # The base was pure black; annotations must have introduced non-black pixels.
    assert out.max() > 0


def test_delete_selected_removes_only_annotations(qapp):
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QColor

    from snappr.annotate import AnnotationView, RectAnnotation

    base = np.zeros((80, 80, 3), dtype=np.uint8)
    view = AnnotationView(base, QColor("#FF0000"), 3)

    rect = RectAnnotation(QColor("#FF0000"), 3)
    rect.setRect(QRectF(5, 5, 20, 20))
    view._scene.addItem(rect)
    rect.setSelected(True)

    before = len(view._scene.items())
    view.delete_selected()
    after = len(view._scene.items())

    assert after == before - 1
    # Base pixmap must survive.
    assert view._base_item in view._scene.items()
