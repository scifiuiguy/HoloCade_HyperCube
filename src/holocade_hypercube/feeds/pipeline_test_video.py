# Copyright (c) 2025 AJ Campbell. Licensed under the MIT License.
"""Pipeline test video harness: play a synchronized L/R video pair.

Intended use:
- Drop two files into `pipeline-test-videos/` (gitignored).
- Configure `feed_mode: pipeline_test_video` and the filenames.
- Optional frame offset to align a rough manual sync.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from holocade_hypercube.calibration.stereo_json import StereoRectifier


@dataclass
class PipelineTestVideoConfig:
    videos_dir: Path
    left_name: str
    right_name: str
    offset_frames: int
    loop: bool

    @staticmethod
    def from_cfg(cfg: dict) -> "PipelineTestVideoConfig":
        videos_dir = Path(str(cfg.get("pipeline_test_videos_dir", "pipeline-test-videos")))
        left_name = str(cfg.get("pipeline_test_left_video", "left.mp4"))
        right_name = str(cfg.get("pipeline_test_right_video", "right.mp4"))
        offset_frames = int(cfg.get("pipeline_test_video_offset_frames", 0))
        loop = bool(cfg.get("pipeline_test_video_loop", True))
        return PipelineTestVideoConfig(
            videos_dir=videos_dir,
            left_name=left_name,
            right_name=right_name,
            offset_frames=offset_frames,
            loop=loop,
        )


class PipelineTestVideoPlayer:
    def __init__(self, cfg: PipelineTestVideoConfig):
        self._cfg = cfg
        self._cap_l = self._open(cfg.videos_dir / cfg.left_name, label="left")
        self._cap_r = self._open(cfg.videos_dir / cfg.right_name, label="right")
        self._started = False

    def _open(self, path: Path, *, label: str) -> cv2.VideoCapture:
        if not path.is_file():
            raise FileNotFoundError(f"pipeline_test_video missing {label} video: {path}")
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise RuntimeError(f"failed to open {label} video: {path}")
        return cap

    def close(self) -> None:
        if self._cap_l is not None:
            self._cap_l.release()
        if self._cap_r is not None:
            self._cap_r.release()

    def _rewind(self) -> None:
        self._cap_l.set(cv2.CAP_PROP_POS_FRAMES, 0)
        self._cap_r.set(cv2.CAP_PROP_POS_FRAMES, 0)
        self._started = False

    def _apply_offset_once(self) -> None:
        if self._started:
            return
        self._started = True
        off = int(self._cfg.offset_frames)
        if off == 0:
            return
        # Positive offset means "right lags", so advance right.
        cap = self._cap_r if off > 0 else self._cap_l
        steps = abs(off)
        for _ in range(steps):
            ok, _frame = cap.read()
            if not ok:
                if self._cfg.loop:
                    self._rewind()
                    return
                raise EOFError("pipeline_test_video offset seeks past EOF")

    def read_pair(self) -> tuple[np.ndarray, np.ndarray]:
        self._apply_offset_once()
        ok_l, left = self._cap_l.read()
        ok_r, right = self._cap_r.read()
        if ok_l and ok_r:
            return left, right

        if not self._cfg.loop:
            raise EOFError("pipeline_test_video reached EOF")
        self._rewind()
        self._apply_offset_once()
        ok_l, left = self._cap_l.read()
        ok_r, right = self._cap_r.read()
        if not (ok_l and ok_r):
            raise EOFError("pipeline_test_video could not read after rewind")
        return left, right


def pipeline_test_video_frames(
    player: PipelineTestVideoPlayer,
    *,
    cell_width: int,
    cell_height: int,
    rectifier: StereoRectifier | None,
    fit_to_cell_same_orientation,
) -> list[np.ndarray]:
    left, right = player.read_pair()
    if rectifier is not None and rectifier.active:
        left, right = rectifier.rectify_pair(left, right)
    left = fit_to_cell_same_orientation(left, cell_width, cell_height)
    right = fit_to_cell_same_orientation(right, cell_width, cell_height)
    return [left, right, left, right, left, right, left, right]

