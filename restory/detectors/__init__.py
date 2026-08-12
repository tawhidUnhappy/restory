"""restory.detectors — Detection algorithms for manga and webtoon panel segmentation."""

from __future__ import annotations

from restory.detectors.heuristic import (
    detect_heuristic,
    sort_reading_order,
    clamp_box,
    is_blank_or_sliver,
    collect_images,
)
from restory.detectors.magi import detect_magi
from restory.detectors.webtoon import detect_webtoon
from restory.detectors.hybrid import detect_hybrid

__all__ = [
    "detect_heuristic",
    "detect_magi",
    "detect_webtoon",
    "detect_hybrid",
    "sort_reading_order",
    "clamp_box",
    "is_blank_or_sliver",
    "collect_images",
]