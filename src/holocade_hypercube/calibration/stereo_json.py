# Copyright (c) 2025 AJ Campbell. Licensed under the MIT License.
"""Load stereo calibration from JSON and apply OpenCV stereo rectification + undistort remap."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np


def _to_camera_matrix(key: str, data: dict) -> np.ndarray:
    raw = data[key]
    arr = np.asarray(raw, dtype=np.float64)
    if arr.shape != (3, 3):
        raise ValueError(f"{key} must be 3x3, got {arr.shape}")
    return arr


def _to_distortion(key: str, data: dict) -> np.ndarray:
    raw = data[key]
    arr = np.asarray(raw, dtype=np.float64).reshape(-1)
    if arr.size not in (4, 5, 8, 12, 14):
        raise ValueError(f"{key} must have 4,5,8,12, or 14 coeffs, got {arr.size}")
    return arr


def _to_rotation(key: str, data: dict) -> np.ndarray:
    raw = data[key]
    arr = np.asarray(raw, dtype=np.float64)
    if arr.shape != (3, 3):
        raise ValueError(f"{key} must be 3x3, got {arr.shape}")
    return arr


def _to_translation(key: str, data: dict) -> np.ndarray:
    raw = data[key]
    arr = np.asarray(raw, dtype=np.float64).reshape(-1)
    if arr.size != 3:
        raise ValueError(f"{key} must have length 3, got {arr.size}")
    return arr.reshape(3, 1)


def load_stereo_calibration_json(path: Path) -> dict:
    """Parse calibration JSON; returns arrays suitable for cv2.stereoRectify."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    cal_w = int(data["calibration_image_width"])
    cal_h = int(data["calibration_image_height"])
    if cal_w <= 0 or cal_h <= 0:
        raise ValueError("calibration_image_width/height must be positive")

    K1 = _to_camera_matrix("K_left", data)
    K2 = _to_camera_matrix("K_right", data)
    D1 = _to_distortion("D_left", data)
    D2 = _to_distortion("D_right", data)
    R = _to_rotation("R", data)
    T = _to_translation("T", data)

    return {
        "image_size": (cal_w, cal_h),
        "K1": K1,
        "K2": K2,
        "D1": D1,
        "D2": D2,
        "R": R,
        "T": T,
    }


class StereoRectifier:
    """
    Precomputes undistort+rectify maps from a stereo calibration JSON file.
    When inactive (no file / mode none), rectify_pair returns inputs unchanged.
    """

    __slots__ = ("_active", "_cal_size", "_map1x", "_map1y", "_map2x", "_map2y", "_Q")

    def __init__(self, calibration_path: Path | None):
        self._active = False
        self._cal_size = (0, 0)
        self._map1x = self._map1y = self._map2x = self._map2y = None
        self._Q = None

        if calibration_path is None or not calibration_path.is_file():
            return

        cal = load_stereo_calibration_json(calibration_path)
        cal_w, cal_h = cal["image_size"]

        R1, R2, P1, P2, Q, _roi1, _roi2 = cv2.stereoRectify(
            cal["K1"],
            cal["D1"],
            cal["K2"],
            cal["D2"],
            (cal_w, cal_h),
            cal["R"],
            cal["T"],
            flags=cv2.CALIB_ZERO_DISPARITY,
        )

        self._map1x, self._map1y = cv2.initUndistortRectifyMap(
            cal["K1"], cal["D1"], R1, P1, (cal_w, cal_h), cv2.CV_32FC1
        )
        self._map2x, self._map2y = cv2.initUndistortRectifyMap(
            cal["K2"], cal["D2"], R2, P2, (cal_w, cal_h), cv2.CV_32FC1
        )
        self._cal_size = (cal_w, cal_h)
        self._Q = Q
        self._active = True

    @property
    def active(self) -> bool:
        return self._active

    @property
    def calibration_size(self) -> tuple[int, int]:
        """(width, height) images must match before remap (after resize if needed)."""
        return self._cal_size

    @property
    def Q(self) -> np.ndarray | None:
        """4x4 reprojection matrix from cv2.stereoRectify (None when inactive)."""
        return self._Q

    def rectify_pair(self, left_bgr: np.ndarray, right_bgr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        if not self._active:
            return left_bgr, right_bgr

        cal_w, cal_h = self._cal_size
        if left_bgr.shape[:2] != (cal_h, cal_w):
            left_bgr = cv2.resize(left_bgr, (cal_w, cal_h), interpolation=cv2.INTER_AREA)
        if right_bgr.shape[:2] != (cal_h, cal_w):
            right_bgr = cv2.resize(right_bgr, (cal_w, cal_h), interpolation=cv2.INTER_AREA)

        left_out = cv2.remap(
            left_bgr, self._map1x, self._map1y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT
        )
        right_out = cv2.remap(
            right_bgr, self._map2x, self._map2y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT
        )
        return left_out, right_out


def stereo_rectifier_from_config(cfg: dict) -> StereoRectifier:
    """
    stereo_rectify_mode:
      - none (default): no rectification
      - stereo_json: load stereo_calibration_json (path relative to cwd unless absolute)
    """
    mode = str(cfg.get("stereo_rectify_mode", "none")).strip().lower()
    if mode == "none":
        return StereoRectifier(None)
    if mode != "stereo_json":
        raise ValueError(f"unsupported stereo_rectify_mode: {mode}")

    raw = cfg.get("stereo_calibration_json")
    if not raw:
        raise ValueError("stereo_calibration_json is required when stereo_rectify_mode is stereo_json")

    path = Path(str(raw))
    if not path.is_file():
        raise FileNotFoundError(f"stereo calibration JSON not found: {path.resolve()}")

    return StereoRectifier(path)
