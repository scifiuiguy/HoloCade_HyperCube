import sys
import unittest
from pathlib import Path

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _REPO_ROOT / "src"
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from holocade_hypercube.atlas.packer import pack_four_by_two
from holocade_hypercube.quadrants.split import four_vertical_bands


class AtlasLayoutTests(unittest.TestCase):
    def test_pack_four_by_two_supports_portrait_cells(self):
        cell_w = 720
        cell_h = 1280
        frames = [np.full((cell_h, cell_w, 3), i, dtype=np.uint8) for i in range(8)]
        atlas = pack_four_by_two(frames, cell_width=cell_w, cell_height=cell_h)
        self.assertEqual(atlas.shape[:2], (cell_h * 2, cell_w * 4))
        self.assertEqual(int(atlas[10, 10, 0]), 0)
        self.assertEqual(int(atlas[cell_h + 10, cell_w * 3 + 10, 0]), 7)

    def test_four_vertical_bands_defaults_to_cell_resolution(self):
        cell_w = 1280
        cell_h = 720
        frames = [np.full((cell_h, cell_w, 3), i, dtype=np.uint8) for i in range(8)]
        atlas = pack_four_by_two(frames, cell_width=cell_w, cell_height=cell_h)
        quads = four_vertical_bands(atlas, cell_width=cell_w, cell_height=cell_h)
        self.assertEqual(len(quads), 4)
        for q in quads:
            self.assertEqual(q.shape[:2], (cell_h, cell_w))


if __name__ == "__main__":
    unittest.main()
