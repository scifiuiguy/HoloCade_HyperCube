import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _REPO_ROOT / "src"
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from holocade_hypercube.calibration.stereo_json import (
    StereoRectifier,
    load_stereo_calibration_json,
    stereo_rectifier_from_config,
)

_EXAMPLE_CAL = _REPO_ROOT / "calibration" / "example_stereo_pair.json"


class StereoJsonTests(unittest.TestCase):
    def test_example_json_loads(self):
        cal = load_stereo_calibration_json(_EXAMPLE_CAL)
        self.assertEqual(cal["image_size"], (720, 1280))
        self.assertEqual(cal["K1"].shape, (3, 3))

    def test_rectifier_from_example_is_active(self):
        r = StereoRectifier(_EXAMPLE_CAL)
        self.assertTrue(r.active)
        self.assertEqual(r.calibration_size, (720, 1280))

    def test_mode_none_is_inactive(self):
        r = stereo_rectifier_from_config({"stereo_rectify_mode": "none"})
        self.assertFalse(r.active)
        l = np.zeros((10, 10, 3), dtype=np.uint8)
        lo, ro = r.rectify_pair(l, l.copy())
        self.assertIs(lo, l)

    def test_rectify_pair_output_shape(self):
        r = StereoRectifier(_EXAMPLE_CAL)
        h, w = 1280, 720
        left = np.zeros((h, w, 3), dtype=np.uint8)
        left[100:200, 100:200] = (255, 0, 0)
        right = np.zeros((h, w, 3), dtype=np.uint8)
        lo, ro = r.rectify_pair(left, right)
        self.assertEqual(lo.shape, (h, w, 3))
        self.assertEqual(ro.shape, (h, w, 3))

    def test_stereo_json_mode_requires_path(self):
        with self.assertRaises(ValueError):
            stereo_rectifier_from_config({"stereo_rectify_mode": "stereo_json"})

    def test_temp_identity_calibration(self):
        payload = {
            "calibration_image_width": 64,
            "calibration_image_height": 48,
            "K_left": [[40.0, 0.0, 32.0], [0.0, 40.0, 24.0], [0.0, 0.0, 1.0]],
            "K_right": [[40.0, 0.0, 32.0], [0.0, 40.0, 24.0], [0.0, 0.0, 1.0]],
            "D_left": [0.0, 0.0, 0.0, 0.0, 0.0],
            "D_right": [0.0, 0.0, 0.0, 0.0, 0.0],
            "R": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "T": [0.05, 0.0, 0.0],
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(payload, f)
            path = Path(f.name)
        try:
            r = StereoRectifier(path)
            self.assertTrue(r.active)
            left = np.arange(48 * 64 * 3, dtype=np.uint8).reshape(48, 64, 3)
            right = left.copy()
            lo, ro = r.rectify_pair(left, right)
            self.assertEqual(lo.shape, (48, 64, 3))
            self.assertEqual(ro.shape, (48, 64, 3))
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
