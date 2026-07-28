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


def test_oval_renders_as_an_unfilled_shape(qapp):
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QColor

    from snappr.annotate import AnnotationView, OvalAnnotation

    base = np.zeros((100, 120, 3), dtype=np.uint8)
    view = AnnotationView(base, QColor("#FF0000"), 4)

    oval = OvalAnnotation(QColor("#FF0000"), 4)
    oval.setRect(QRectF(20, 20, 60, 40))
    view._scene.addItem(oval)

    out = view.render_to_rgb()

    assert out[20:24, 47:53].max() > 0
    assert np.array_equal(out[40, 50], base[40, 50])


def test_pixelate_follows_item_position_and_only_changes_its_region(qapp):
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QColor

    from snappr.annotate import AnnotationView, PixelateAnnotation

    y, x = np.indices((100, 180))
    checker = ((x // 4 + y // 4) % 2 * 255).astype(np.uint8)
    base = np.repeat(checker[..., None], 3, axis=2)
    view = AnnotationView(base, QColor("#FF0000"), 3)

    pixelate = PixelateAnnotation(view._get_pixelated_base())
    pixelate.setRect(QRectF(20, 20, 60, 40))
    view._scene.addItem(pixelate)

    first = view.render_to_rgb()
    pixelated_region = first[25:55, 25:75]
    assert pixelated_region.std() < base[25:55, 25:75].std() * 0.1
    assert len(np.unique(pixelated_region.reshape(-1, 3), axis=0)) <= 8
    assert np.array_equal(first[:15], base[:15])

    pixelate.setPos(90, 20)
    moved = view.render_to_rgb()
    assert np.array_equal(moved[20:60, 20:80], base[20:60, 20:80])
    assert moved[45:75, 115:165].std() < base[45:75, 115:165].std() * 0.1


def test_selected_box_can_be_resized_from_a_handle(qapp):
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor
    from PySide6.QtTest import QTest

    from snappr.annotate import AnnotationView, RectAnnotation

    base = np.zeros((200, 240, 3), dtype=np.uint8)
    view = AnnotationView(base, QColor("#FF0000"), 3)
    view.resize(260, 220)
    view.show()
    qapp.processEvents()

    rect = RectAnnotation(QColor("#FF0000"), 3)
    rect.setRect(QRectF(30, 30, 80, 60))
    view._scene.addItem(rect)
    rect.setSelected(True)
    qapp.processEvents()

    assert len(rect._handle_rects()) == 8
    start = view.mapFromScene(QPointF(110, 90))
    end = view.mapFromScene(QPointF(145, 120))
    QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(view.viewport(), end)
    QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=end)
    qapp.processEvents()

    assert rect.rect().width() == pytest.approx(115)
    assert rect.rect().height() == pytest.approx(90)
    assert rect.isSelected()
    view.close()


def test_resize_handles_are_not_flattened_and_selection_is_restored(qapp):
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QColor

    from snappr.annotate import AnnotationView, OvalAnnotation

    base = np.zeros((100, 120, 3), dtype=np.uint8)
    view = AnnotationView(base, QColor("#FF0000"), 3)
    oval = OvalAnnotation(QColor("#FF0000"), 3)
    oval.setRect(QRectF(20, 20, 60, 40))
    view._scene.addItem(oval)
    oval.setSelected(True)

    selected_output = view.render_to_rgb()
    assert oval.isSelected()

    oval.setSelected(False)
    plain_output = view.render_to_rgb()
    assert np.array_equal(selected_output, plain_output)


def test_counter_tool_adds_sequential_movable_markers(qapp):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QColor
    from PySide6.QtTest import QTest

    from snappr.annotate import AnnotationView, CounterAnnotation, Tool

    base = np.zeros((180, 240, 3), dtype=np.uint8)
    view = AnnotationView(base, QColor("#FF3B30"), 3)
    view.resize(260, 200)
    view.show()
    qapp.processEvents()
    view.set_tool(Tool.COUNTER)

    for point in (QPointF(50, 60), QPointF(130, 110)):
        QTest.mouseClick(
            view.viewport(),
            Qt.MouseButton.LeftButton,
            pos=view.mapFromScene(point),
        )
        qapp.processEvents()

    counters = sorted(
        (
            item
            for item in view._scene.items()
            if isinstance(item, CounterAnnotation)
        ),
        key=lambda item: item.number,
    )
    assert [item.number for item in counters] == [1, 2]
    assert view._tool == Tool.COUNTER

    # Switching to Select allows a marker to be repositioned.
    view.set_tool(Tool.SELECT)
    start = view.mapFromScene(QPointF(50, 60))
    end = view.mapFromScene(QPointF(75, 85))
    QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(view.viewport(), end)
    QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=end)
    qapp.processEvents()
    assert counters[0].pos() == QPointF(75, 85)
    assert counters[0].isSelected()

    # Selection decoration stays in the editor and the fill color is editable.
    view.set_color(QColor("#00AA44"))
    selected_output = view.render_to_rgb()
    assert counters[0].isSelected()
    counters[0].setSelected(False)
    plain_output = view.render_to_rgb()
    assert np.array_equal(selected_output, plain_output)
    assert plain_output[85, 87, 1] > plain_output[85, 87, 0]
    view.close()


def test_counter_marker_can_be_resized_while_staying_circular(qapp):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QColor
    from PySide6.QtTest import QTest

    from snappr.annotate import AnnotationView, CounterAnnotation

    base = np.zeros((220, 260, 3), dtype=np.uint8)
    view = AnnotationView(base, QColor("#FF3B30"), 3)
    view.resize(280, 240)
    view.show()
    qapp.processEvents()

    counter = CounterAnnotation(1, QColor("#FF3B30"))
    counter.setPos(100, 100)
    view._scene.addItem(counter)
    counter.setSelected(True)
    qapp.processEvents()

    assert len(counter._handle_rects()) == 4
    start = view.mapFromScene(QPointF(118, 118))
    end = view.mapFromScene(QPointF(138, 138))
    QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(view.viewport(), end)
    QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=end)
    qapp.processEvents()

    assert counter.diameter == pytest.approx(56)
    assert counter.pos() == QPointF(110, 110)
    shape_bounds = counter.shape().boundingRect()
    assert shape_bounds.width() == pytest.approx(shape_bounds.height())
    assert counter.isSelected()
    view.close()


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
