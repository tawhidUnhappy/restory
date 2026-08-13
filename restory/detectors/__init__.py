"""restory.detectors — Detection algorithms for manga and webtoon panel segmentation."""

from __future__ import annotations

from restory.detectors.heuristic import (
    detect_japanese_paged,
    detect_heuristic,
    sort_reading_order,
    clamp_box,
    is_blank_or_sliver,
    collect_images,
    otsu_threshold,
    snap_box_to_content,
)
from restory.detectors.magi import detect_magi, detect_magi_batch
from restory.detectors.webtoon import detect_webtoon

__all__ = [
    "detect_japanese_paged",
    "detect_heuristic",
    "detect_magi",
    "detect_magi_batch",
    "detect_webtoon",
    "sort_reading_order",
    "clamp_box",
    "is_blank_or_sliver",
    "collect_images",
    "otsu_threshold",
    "snap_box_to_content",
]