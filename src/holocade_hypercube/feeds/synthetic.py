# Copyright (c) 2025 AJ Campbell. Licensed under the MIT License.

from __future__ import annotations

import numpy as np

# Distinct BGR swatches per logical camera (no OpenCV dependency here).
_SWATCHES: list[tuple[int, int, int]] = [
    (40, 40, 200),
    (40, 200, 40),
    (200, 40, 40),
    (40, 200, 200),
    (200, 40, 200),
    (200, 200, 40),
    (120, 60, 200),
    (60, 200, 120),
]


def synthetic_frame(index: int, width: int = 1280, height: int = 720) -> np.ndarray:
    """BGR uint8 image with a distinct solid color per logical camera index (0..7)."""
    bgr = np.empty((height, width, 3), dtype=np.uint8)
    bgr[:] = _SWATCHES[index % len(_SWATCHES)]
    return bgr
