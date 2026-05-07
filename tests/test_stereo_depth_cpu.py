import sys
import unittest
from pathlib import Path

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _REPO_ROOT / "src"
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from holocade_hypercube.stereo_depth import StereoDepthConfig, StereoDepthEstimatorCpuSgbm


class StereoDepthCpuTests(unittest.TestCase):
    def test_disparity_detects_known_shift(self):
        # Synthetic textured image: random noise block.
        h, w = 160, 240
        rng = np.random.default_rng(123)
        left = (rng.random((h, w, 3)) * 255).astype(np.uint8)

        # Right image is shifted left by d pixels -> positive disparity ~ d.
        d = 12
        right = np.zeros_like(left)
        right[:, : w - d] = left[:, d:]

        cfg = StereoDepthConfig.from_cfg(
            {
                "stereo_depth_downscale": 1.0,
                "stereo_depth_min_disparity": 0,
                "stereo_depth_num_disparities": 64,
                "stereo_depth_block_size": 7,
                "stereo_depth_valid_frac_threshold": 0.01,
                "stereo_depth_min_depth_m": 0.1,
                "stereo_depth_max_depth_m": 10.0,
            }
        )
        est = StereoDepthEstimatorCpuSgbm(cfg)
        res = est.estimate(left, right, Q=None, roi_cfg={})

        self.assertEqual(res.disparity_px.shape, (h, w))
        self.assertIsNone(res.depth_z_m)

        valid = res.valid_mask
        self.assertGreater(valid.mean(), 0.2)

        # Robustly estimate disparity from valid pixels; allow tolerance due to SGBM noise.
        med = float(np.median(res.disparity_px[valid]))
        self.assertTrue(abs(med - d) <= 2.5, f"median disparity {med} not close to expected {d}")

    def test_oob_gate_fails_on_blank_images(self):
        h, w = 120, 160
        left = np.zeros((h, w, 3), dtype=np.uint8)
        right = np.zeros((h, w, 3), dtype=np.uint8)

        cfg = StereoDepthConfig.from_cfg(
            {
                "stereo_depth_downscale": 1.0,
                "stereo_depth_num_disparities": 64,
                "stereo_depth_valid_frac_threshold": 0.05,
                "stereo_depth_min_depth_m": 0.1,
                "stereo_depth_max_depth_m": 10.0,
            }
        )
        est = StereoDepthEstimatorCpuSgbm(cfg)
        res = est.estimate(left, right, Q=None, roi_cfg={})
        self.assertFalse(res.in_bounds)


if __name__ == "__main__":
    unittest.main()

