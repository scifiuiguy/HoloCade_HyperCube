# Copyright (c) 2025 AJ Campbell. Licensed under the MIT License.

from __future__ import annotations

import numpy as np

from holocade_hypercube.atlas.packer import CELL_H, CELL_W


def four_vertical_bands(
    atlas_bgr: np.ndarray,
    cell_width: int = CELL_W,
    cell_height: int = CELL_H,
    out_width: int | None = None,
    out_height: int | None = None,
) -> list[np.ndarray]:
    """
    Split atlas into four equal vertical bands (placeholder mapping; remappable later).
    Each band is resized to (out_width, out_height) BGR for transport.
    Defaults to configured cell size.
    """
    import cv2

    expected_h = cell_height * 2
    expected_w = cell_width * 4
    if atlas_bgr.shape[0] != expected_h or atlas_bgr.shape[1] != expected_w:
        raise ValueError(f"atlas expected {(expected_h, expected_w)}, got {atlas_bgr.shape[:2]}")
    out_w = cell_width if out_width is None else int(out_width)
    out_h = cell_height if out_height is None else int(out_height)
    band_w = expected_w // 4
    out: list[np.ndarray] = []
    for q in range(4):
        x0 = q * band_w
        x1 = (q + 1) * band_w
        crop = atlas_bgr[:, x0:x1]
        resized = cv2.resize(crop, (out_w, out_h), interpolation=cv2.INTER_AREA)
        out.append(resized)
    return out
