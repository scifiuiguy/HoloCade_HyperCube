# Copyright (c) 2025 AJ Campbell. Licensed under the MIT License.

from __future__ import annotations

import numpy as np

from holocade_hypercube.atlas.packer import ATLAS_H, ATLAS_W


def four_vertical_bands(atlas_bgr: np.ndarray, out_height: int = 720) -> list[np.ndarray]:
    """
    Split atlas into four equal vertical bands (placeholder mapping; remappable later).
    Each band is resized to (1280, out_height) BGR for MJPEG-friendly payloads.
    """
    import cv2

    if atlas_bgr.shape[0] != ATLAS_H or atlas_bgr.shape[1] != ATLAS_W:
        raise ValueError(f"atlas expected {(ATLAS_H, ATLAS_W)}, got {atlas_bgr.shape[:2]}")
    band_w = ATLAS_W // 4
    out: list[np.ndarray] = []
    for q in range(4):
        x0 = q * band_w
        x1 = (q + 1) * band_w
        crop = atlas_bgr[:, x0:x1]
        resized = cv2.resize(crop, (1280, out_height), interpolation=cv2.INTER_AREA)
        out.append(resized)
    return out
