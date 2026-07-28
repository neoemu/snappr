"""Vertical image stitching for scrolling screenshots.

The :class:`ScrollStitcher` accumulates frames of a *fixed* screen region
captured while the user scrolls content (typically downward). Each new frame
overlaps the previous one; the stitcher finds the vertical offset of that
overlap via normalized template matching and appends only the newly revealed
strip, producing a single tall image with no duplicated content.

Assumptions / limitations (documented in the plan):
- The capture region is fixed on screen; only the *content* scrolls.
- Works best with downward scrolling. Frames that don't move or cannot be
  matched confidently are ignored rather than merged.
- Fixed headers/footers or floating scrollbars inside the region can confuse
  matching; keep the region within the scrolling viewport for best results.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class StitchResult:
    appended_pixels: int  # new rows added by this frame (0 == ignored)
    offset: int           # detected vertical shift of new frame vs. canvas
    confidence: float     # match score in [0, 1]
    accepted: bool        # whether the frame contributed new content


class ScrollStitcher:
    """Incrementally builds a tall image from overlapping region frames."""

    def __init__(
        self,
        anchor_height: int = 60,
        min_confidence: float = 0.6,
        min_step: int = 2,
        horizontal_margin_ratio: float = 0.04,
    ) -> None:
        # Height (px) of the anchor strip taken from the bottom of the canvas
        # and searched for inside the new frame.
        self.anchor_height = anchor_height
        # Minimum normalized-correlation score to trust a match.
        self.min_confidence = min_confidence
        # Minimum number of new rows for a frame to count as progress.
        self.min_step = min_step
        # Ignore a thin strip on both sides while matching; scrollbars, shadows
        # and floating chrome commonly live there and can destabilize matches.
        self.horizontal_margin_ratio = max(0.0, min(horizontal_margin_ratio, 0.45))

        self._canvas: np.ndarray | None = None

    @property
    def canvas(self) -> np.ndarray | None:
        return self._canvas

    @property
    def height(self) -> int:
        return 0 if self._canvas is None else self._canvas.shape[0]

    def result(self) -> np.ndarray | None:
        return self._canvas

    def add_frame(self, frame: np.ndarray) -> StitchResult:
        """Feed a new region frame; returns what (if anything) was appended."""
        frame = np.ascontiguousarray(frame)

        if self._canvas is None:
            self._canvas = frame.copy()
            return StitchResult(frame.shape[0], 0, 1.0, True)

        # Width mismatch: region changed shape — replace canvas defensively.
        if frame.shape[1] != self._canvas.shape[1]:
            self._canvas = frame.copy()
            return StitchResult(frame.shape[0], 0, 1.0, True)

        offset, confidence = self._find_offset(frame)

        if confidence < self.min_confidence:
            # No reliable overlap found. Appending the whole frame creates the
            # broken "stacked screenshots" effect, so wait for a better frame.
            return StitchResult(0, offset, confidence, False)

        new_rows = frame.shape[0] - offset
        if new_rows < self.min_step:
            # Frame essentially identical (no scroll) or scrolled upward.
            return StitchResult(0, offset, confidence, False)

        strip = frame[offset:, :, :]
        self._canvas = np.vstack([self._canvas, strip])
        return StitchResult(strip.shape[0], offset, confidence, True)

    def _find_offset(self, frame: np.ndarray) -> tuple[int, float]:
        """Locate the canvas's bottom anchor strip within ``frame``.

        Returns ``(offset, confidence)`` where ``offset`` is the y-position in
        ``frame`` where content matching the canvas bottom begins. New content
        is everything in ``frame`` below ``offset + anchor_height``... but we
        return the top of the matched anchor, so callers append ``frame[offset:]``
        only after accounting for the anchor — here we define ``offset`` as the
        first NEW row, i.e. matched_y + anchor_height.
        """
        canvas = self._canvas
        assert canvas is not None

        max_anchor_h = min(canvas.shape[0], frame.shape[0])
        if max_anchor_h < 1:
            return frame.shape[0], 0.0

        frame_search = self._crop_matching_columns(frame)
        frame_g = cv2.cvtColor(frame_search, cv2.COLOR_RGB2GRAY)
        best_offset = frame.shape[0]
        best_confidence = -1.0

        # Grayscale improves robustness and speed for matching. Try multiple
        # bottom-anchor heights so faster scrolls with small remaining overlap
        # can still be stitched instead of truncating the capture.
        for anchor_h in self._anchor_heights(max_anchor_h):
            anchor = canvas[-anchor_h:, :, :]
            anchor = self._crop_matching_columns(anchor)
            anchor_g = cv2.cvtColor(anchor, cv2.COLOR_RGB2GRAY)

            # Search for the anchor anywhere vertically in the frame.
            res = cv2.matchTemplate(frame_g, anchor_g, cv2.TM_CCOEFF_NORMED)
            _min_val, max_val, _min_loc, max_loc = cv2.minMaxLoc(res)
            matched_y = max_loc[1]

            # First new row sits right below the matched anchor region.
            first_new_row = matched_y + anchor_h
            first_new_row = max(0, min(first_new_row, frame.shape[0]))
            if max_val > best_confidence:
                best_offset = first_new_row
                best_confidence = float(max_val)
            if max_val >= self.min_confidence:
                return first_new_row, float(max_val)

        return best_offset, best_confidence

    def _anchor_heights(self, max_anchor_h: int) -> list[int]:
        candidates = [
            self.anchor_height,
            int(self.anchor_height * 0.75),
            int(self.anchor_height * 0.5),
            int(self.anchor_height * 0.35),
            16,
        ]
        heights = []
        for candidate in candidates:
            height = max(8, min(candidate, max_anchor_h))
            if height not in heights:
                heights.append(height)
        return heights

    def _crop_matching_columns(self, image: np.ndarray) -> np.ndarray:
        width = image.shape[1]
        margin = int(width * self.horizontal_margin_ratio)
        if margin <= 0 or width - (2 * margin) < 16:
            return image
        return image[:, margin : width - margin, :]
