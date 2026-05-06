# Copyright (c) 2025 AJ Campbell. Licensed under the MIT License.

from __future__ import annotations

import numpy as np

ATLAS_W = 5120
ATLAS_H = 2880
CELL_W = 1280
CELL_H = 720


def pack_four_by_two(
    frames_bgr: list[np.ndarray],
    cell_width: int = CELL_W,
    cell_height: int = CELL_H,
) -> np.ndarray:
    """
    Pack eight BGR frames into a 4x2 atlas.
    Order: row-major cell index 0..7 maps to (col,row) = (i%4, i//4).
    """
    if len(frames_bgr) != 8:
        raise ValueError(f"expected 8 frames, got {len(frames_bgr)}")
    if cell_width <= 0 or cell_height <= 0:
        raise ValueError(f"invalid cell size ({cell_width}, {cell_height})")
    atlas_w = cell_width * 4
    atlas_h = cell_height * 2
    atlas = np.zeros((atlas_h, atlas_w, 3), dtype=np.uint8)
    for i, frame in enumerate(frames_bgr):
        if frame.shape[0] != cell_height or frame.shape[1] != cell_width:
            raise ValueError(f"frame {i} expected ({cell_height},{cell_width}), got {frame.shape[:2]}")
        col, row = i % 4, i // 4
        y0, y1 = row * cell_height, (row + 1) * cell_height
        x0, x1 = col * cell_width, (col + 1) * cell_width
        atlas[y0:y1, x0:x1] = frame
    return atlas
