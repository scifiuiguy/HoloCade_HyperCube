# Copyright (c) 2025 AJ Campbell. Licensed under the MIT License.
"""Stereo depth estimation utilities (CPU fallback for v0.0.5).

Primary outputs:
- disparity (float32 pixels)
- depth_z_m (float32 meters) via cv2.reprojectImageTo3D + Q from stereoRectify
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


def _round_num_disparities(x: int) -> int:
    x = int(x)
    if x <= 0:
        raise ValueError("num_disparities must be > 0")
    # OpenCV requires multiple of 16.
    return ((x + 15) // 16) * 16


def _parse_roi(cfg: dict, image_w: int, image_h: int) -> tuple[int, int, int, int] | None:
    """
    stereo_depth_roi: [x, y, w, h] in pixels, in *cell/rectified* coordinates.
    If omitted, use full frame.
    """
    raw = cfg.get("stereo_depth_roi")
    if raw is None:
        # Optional ROI policy default.
        policy = str(cfg.get("stereo_depth_roi_policy", "full")).strip().lower()
        if policy in ("full", "none"):
            return None
        if policy == "sixths_overlap":
            # Frame split into 3 vertical bands (top/middle/bottom) and 2 horizontal bands (left/right).
            # Face expectation: left cam -> middle-right, right cam -> middle-left.
            # For depth we pick the *overlap-friendly* band: middle third vertically and center half horizontally.
            y = image_h // 3
            h = max(1, image_h // 3)
            x = image_w // 4
            w = max(1, image_w // 2)
            return x, y, w, h
        raise ValueError(f"unsupported stereo_depth_roi_policy: {policy}")
    if not isinstance(raw, (list, tuple)) or len(raw) != 4:
        raise ValueError("stereo_depth_roi must be [x,y,w,h] in pixels")
    x, y, w, h = (int(v) for v in raw)
    if w <= 0 or h <= 0:
        raise ValueError("stereo_depth_roi w/h must be positive")
    x = max(0, min(x, image_w - 1))
    y = max(0, min(y, image_h - 1))
    w = max(1, min(w, image_w - x))
    h = max(1, min(h, image_h - y))
    return x, y, w, h


@dataclass(frozen=True)
class StereoDepthConfig:
    downscale: float
    min_disparity: int
    num_disparities: int
    block_size: int
    uniqueness_ratio: int
    speckle_window_size: int
    speckle_range: int
    disp12_max_diff: int

    min_depth_m: float
    max_depth_m: float
    valid_frac_threshold: float
    min_disparity_std_px: float

    @staticmethod
    def from_cfg(cfg: dict) -> "StereoDepthConfig":
        downscale = float(cfg.get("stereo_depth_downscale", 0.5))
        if not (0.05 <= downscale <= 1.0):
            raise ValueError("stereo_depth_downscale must be in [0.05, 1.0]")

        min_disp = int(cfg.get("stereo_depth_min_disparity", 0))
        num_disp = _round_num_disparities(int(cfg.get("stereo_depth_num_disparities", 96)))
        block_size = int(cfg.get("stereo_depth_block_size", 7))
        if block_size % 2 == 0 or block_size < 3:
            raise ValueError("stereo_depth_block_size must be odd and >= 3")

        min_depth_m = float(cfg.get("stereo_depth_min_depth_m", 0.6))  # ~2 ft
        max_depth_m = float(cfg.get("stereo_depth_max_depth_m", 0.9))  # ~3 ft
        if min_depth_m <= 0 or max_depth_m <= 0 or min_depth_m >= max_depth_m:
            raise ValueError("stereo_depth_min_depth_m/max_depth_m invalid")

        valid_frac_threshold = float(cfg.get("stereo_depth_valid_frac_threshold", 0.02))
        if not (0.0 <= valid_frac_threshold <= 1.0):
            raise ValueError("stereo_depth_valid_frac_threshold must be in [0,1]")

        min_disp_std = float(cfg.get("stereo_depth_min_disparity_std_px", 0.5))
        if min_disp_std < 0.0:
            raise ValueError("stereo_depth_min_disparity_std_px must be >= 0")

        return StereoDepthConfig(
            downscale=downscale,
            min_disparity=min_disp,
            num_disparities=num_disp,
            block_size=block_size,
            uniqueness_ratio=int(cfg.get("stereo_depth_uniqueness_ratio", 10)),
            speckle_window_size=int(cfg.get("stereo_depth_speckle_window_size", 50)),
            speckle_range=int(cfg.get("stereo_depth_speckle_range", 1)),
            disp12_max_diff=int(cfg.get("stereo_depth_disp12_max_diff", 1)),
            min_depth_m=min_depth_m,
            max_depth_m=max_depth_m,
            valid_frac_threshold=valid_frac_threshold,
            min_disparity_std_px=min_disp_std,
        )


@dataclass(frozen=True)
class StereoDepthResult:
    disparity_px: np.ndarray  # float32, shape (h,w)
    depth_z_m: np.ndarray | None  # float32, meters, shape (h,w)
    valid_mask: np.ndarray  # bool, shape (h,w)
    in_bounds: bool
    roi_xywh: tuple[int, int, int, int]
    scale: float


class StereoDepthEstimatorCpuSgbm:
    def __init__(self, cfg: StereoDepthConfig):
        self._cfg = cfg
        self._matcher = cv2.StereoSGBM_create(
            minDisparity=cfg.min_disparity,
            numDisparities=cfg.num_disparities,
            blockSize=cfg.block_size,
            uniquenessRatio=cfg.uniqueness_ratio,
            speckleWindowSize=cfg.speckle_window_size,
            speckleRange=cfg.speckle_range,
            disp12MaxDiff=cfg.disp12_max_diff,
            P1=8 * 1 * cfg.block_size * cfg.block_size,
            P2=32 * 1 * cfg.block_size * cfg.block_size,
            mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY,
        )

    def estimate(
        self,
        left_bgr: np.ndarray,
        right_bgr: np.ndarray,
        *,
        Q: np.ndarray | None,
        roi_cfg: dict,
    ) -> StereoDepthResult:
        h, w = left_bgr.shape[:2]
        if right_bgr.shape[:2] != (h, w):
            raise ValueError("left/right shapes must match for stereo depth")

        roi = _parse_roi(roi_cfg, image_w=w, image_h=h)
        if roi is None:
            x0, y0, rw, rh = (0, 0, w, h)
        else:
            x0, y0, rw, rh = roi

        left_roi = left_bgr[y0 : y0 + rh, x0 : x0 + rw]
        right_roi = right_bgr[y0 : y0 + rh, x0 : x0 + rw]

        scale = float(self._cfg.downscale)
        if scale != 1.0:
            out_w = max(8, int(round(rw * scale)))
            out_h = max(8, int(round(rh * scale)))
            left_roi = cv2.resize(left_roi, (out_w, out_h), interpolation=cv2.INTER_AREA)
            right_roi = cv2.resize(right_roi, (out_w, out_h), interpolation=cv2.INTER_AREA)

        left_g = cv2.cvtColor(left_roi, cv2.COLOR_BGR2GRAY)
        right_g = cv2.cvtColor(right_roi, cv2.COLOR_BGR2GRAY)

        disp_fixed = self._matcher.compute(left_g, right_g)  # int16, disparity*16
        disp = disp_fixed.astype(np.float32) / 16.0

        # OpenCV invalid sentinel is typically (minDisparity - 1).
        # Treat "valid" as anything at/above minDisparity, regardless of sign.
        invalid_sentinel = float(self._cfg.min_disparity - 1)
        # Also reject non-finite and the exact sentinel itself (common on blank/failed matches).
        valid = np.isfinite(disp) & (disp > (invalid_sentinel + 0.5))

        depth_z = None
        disp_for_stats = disp
        if Q is not None:
            # Q expects pixel coordinates in the *full rectified frame*.
            # If we computed disparity on a cropped ROI (and possibly downscaled), we must:
            # 1) scale disparity back into full-res pixel units
            # 2) upsample back to ROI resolution (rw,rh)
            # 3) paste into a full-frame disparity map at the ROI's (x0,y0) offsets
            inv_scale = 1.0 / max(1e-6, scale)
            disp_full_px_small = disp * inv_scale
            if disp_full_px_small.shape[:2] != (rh, rw):
                disp_full_px_roi = cv2.resize(disp_full_px_small, (rw, rh), interpolation=cv2.INTER_LINEAR)
                valid_roi = cv2.resize(valid.astype(np.uint8), (rw, rh), interpolation=cv2.INTER_NEAREST).astype(bool)
            else:
                disp_full_px_roi = disp_full_px_small
                valid_roi = valid

            full_disp = np.full((h, w), np.nan, dtype=np.float32)
            full_valid = np.zeros((h, w), dtype=bool)
            full_disp[y0 : y0 + rh, x0 : x0 + rw] = disp_full_px_roi
            full_valid[y0 : y0 + rh, x0 : x0 + rw] = valid_roi

            pts3 = cv2.reprojectImageTo3D(full_disp, Q, handleMissingValues=True, ddepth=cv2.CV_32F)
            depth_z = pts3[:, :, 2].astype(np.float32)
            valid = full_valid & np.isfinite(depth_z) & (depth_z > 0.0)
            disp_for_stats = full_disp

        # OOB gate: if depth exists, require enough valid pixels AND median depth in target range.
        in_bounds = True
        valid_frac = float(valid.mean()) if valid.size else 0.0
        if valid_frac < self._cfg.valid_frac_threshold:
            in_bounds = False
        if in_bounds and valid.any():
            disp_std = float(np.std(disp_for_stats[valid]))
            if disp_std < self._cfg.min_disparity_std_px:
                in_bounds = False
        if depth_z is not None and valid.any():
            z_med = float(np.median(depth_z[valid]))
            if not (self._cfg.min_depth_m <= z_med <= self._cfg.max_depth_m):
                in_bounds = False

        return StereoDepthResult(
            disparity_px=disp,
            depth_z_m=depth_z,
            valid_mask=valid,
            in_bounds=in_bounds,
            roi_xywh=(x0, y0, rw, rh),
            scale=scale,
        )


def stereo_depth_estimator_from_config(cfg: dict) -> StereoDepthEstimatorCpuSgbm | None:
    mode = str(cfg.get("stereo_depth_mode", "none")).strip().lower()
    if mode == "none":
        return None
    if mode != "cpu_sgbm":
        raise ValueError(f"unsupported stereo_depth_mode: {mode}")
    return StereoDepthEstimatorCpuSgbm(StereoDepthConfig.from_cfg(cfg))

