# Copyright (c) 2025 AJ Campbell. Licensed under the MIT License.

from __future__ import annotations

import numpy as np

ATLAS_W = 5120
ATLAS_H = 2880
CELL_W = 1280
CELL_H = 720


def pack_four_by_two(frames_bgr: list[np.ndarray]) -> np.ndarray:
    """
    Pack eight BGR frames (1280x720) into a 5120x2880 atlas: 4 columns × 2 rows.
    Order: row-major cell index 0..7 maps to (col,row) = (i%4, i//4).
    """
    if len(frames_bgr) != 8:
        raise ValueError(f"expected 8 frames, got {len(frames_bgr)}")
    atlas = np.zeros((ATLAS_H, ATLAS_W, 3), dtype=np.uint8)
    for i, frame in enumerate(frames_bgr):
        if frame.shape[0] != CELL_H or frame.shape[1] != CELL_W:
            raise ValueError(f"frame {i} expected ({CELL_H},{CELL_W}), got {frame.shape[:2]}")
        col, row = i % 4, i // 4
        y0, y1 = row * CELL_H, (row + 1) * CELL_H
        x0, x1 = col * CELL_W, (col + 1) * CELL_W
        atlas[y0:y1, x0:x1] = frame
    return atlas
