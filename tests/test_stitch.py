"""Smoke tests for the scrolling stitcher."""
import numpy as np

from snappr.stitch import ScrollStitcher


def _make_tall_source(height=900, width=200):
    """A tall image with horizontal stripes so rows are distinguishable."""
    rng = np.random.default_rng(42)
    img = rng.integers(0, 256, size=(height, width, 3), dtype=np.uint8)
    # Add a strong row-varying gradient to make vertical matching reliable.
    grad = np.linspace(0, 255, height, dtype=np.uint8)[:, None, None]
    img = ((img.astype(int) + grad) // 2).astype(np.uint8)
    return img


def test_stitch_reconstructs_full_height():
    src = _make_tall_source(height=900, width=200)
    view_h = 300
    step = 100  # scroll by 100px each frame (200px overlap)

    stitcher = ScrollStitcher()
    y = 0
    while y + view_h <= src.shape[0]:
        frame = src[y : y + view_h, :, :]
        stitcher.add_frame(frame)
        y += step

    result = stitcher.result()
    assert result is not None
    # The stitched height should closely match the scrolled extent.
    expected = (y - step) + view_h
    assert abs(result.shape[0] - expected) <= 4
    assert result.shape[1] == src.shape[1]


def test_stitch_handles_small_overlap_from_faster_scroll():
    src = _make_tall_source(height=700, width=200)
    view_h = 300
    step = 270  # only 30px overlap, below the default 60px anchor height

    stitcher = ScrollStitcher()
    y = 0
    while y + view_h <= src.shape[0]:
        frame = src[y : y + view_h, :, :]
        stitcher.add_frame(frame)
        y += step

    result = stitcher.result()
    assert result is not None
    expected = (y - step) + view_h
    assert abs(result.shape[0] - expected) <= 4


def test_stitch_recovers_after_one_bad_frame_if_overlap_remains():
    src = _make_tall_source(height=900, width=200)
    unrelated = np.random.default_rng(123).integers(
        0,
        256,
        size=(300, 200, 3),
        dtype=np.uint8,
    )
    stitcher = ScrollStitcher(min_confidence=0.9)

    stitcher.add_frame(src[0:300])
    rejected = stitcher.add_frame(unrelated)
    accepted = stitcher.add_frame(src[200:500])

    result = stitcher.result()
    assert result is not None
    assert not rejected.accepted
    assert accepted.accepted
    assert abs(result.shape[0] - 500) <= 4


def test_identical_frames_do_not_grow_canvas():
    src = _make_tall_source(height=300, width=200)
    stitcher = ScrollStitcher()
    stitcher.add_frame(src)
    h1 = stitcher.height
    # Feeding the exact same frame again should add (almost) nothing.
    stitcher.add_frame(src)
    assert stitcher.height == h1


def test_unmatched_frame_is_rejected_instead_of_appended():
    src = _make_tall_source(height=300, width=200)
    unrelated = np.random.default_rng(123).integers(
        0,
        256,
        size=src.shape,
        dtype=np.uint8,
    )
    stitcher = ScrollStitcher(min_confidence=0.9)
    stitcher.add_frame(src)
    h1 = stitcher.height

    res = stitcher.add_frame(unrelated)

    assert not res.accepted
    assert res.appended_pixels == 0
    assert stitcher.height == h1


def test_single_frame_is_preserved():
    src = _make_tall_source(height=120, width=80)
    stitcher = ScrollStitcher()
    stitcher.add_frame(src)
    assert stitcher.result().shape == src.shape
