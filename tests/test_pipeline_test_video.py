import sys
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _REPO_ROOT / "src"
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from holocade_hypercube.feeds.pipeline_test_video import PipelineTestVideoConfig, PipelineTestVideoPlayer


def _write_test_avi(path: Path, *, frames: list[np.ndarray], fps: int = 10) -> None:
    # Use MJPG in AVI for portability in OpenCV tests.
    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    h, w = frames[0].shape[:2]
    out = cv2.VideoWriter(str(path), fourcc, fps, (w, h))
    if not out.isOpened():
        raise RuntimeError("VideoWriter failed to open")
    try:
        for f in frames:
            out.write(f)
    finally:
        out.release()


class PipelineTestVideoTests(unittest.TestCase):
    def test_offset_advances_right(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            # frames encode index in pixel value for easy assertions
            left_frames = [np.full((32, 48, 3), i, dtype=np.uint8) for i in range(10)]
            right_frames = [np.full((32, 48, 3), 100 + i, dtype=np.uint8) for i in range(10)]
            _write_test_avi(d / "l.avi", frames=left_frames)
            _write_test_avi(d / "r.avi", frames=right_frames)

            cfg = PipelineTestVideoConfig(
                videos_dir=d,
                left_name="l.avi",
                right_name="r.avi",
                offset_frames=2,
                loop=False,
            )
            p = PipelineTestVideoPlayer(cfg)
            try:
                l0, r0 = p.read_pair()
                self.assertEqual(int(l0[0, 0, 0]), 0)
                # right advanced by 2 frames
                self.assertEqual(int(r0[0, 0, 0]), 102)
            finally:
                p.close()


if __name__ == "__main__":
    unittest.main()

