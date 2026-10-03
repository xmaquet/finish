import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from camera.overlay import draw_timestamp


class OverlayTest(unittest.TestCase):
    def test_paints_a_black_plate_and_white_text_in_the_top_left(self) -> None:
        frame = np.full((240, 640, 3), 128, np.uint8)
        draw_timestamp(frame, "03/10/2026 10:42:17.533")

        corner = frame[0:40, 0:200]
        self.assertLess(int(corner.min()), 20)
        self.assertTrue(bool(np.any(corner.max(axis=2) > 230)))
        self.assertEqual(int(frame[-1, -1, 0]), 128)

    def test_small_frame_does_not_raise(self) -> None:
        frame = np.full((60, 80, 3), 180, np.uint8)
        draw_timestamp(frame, "03/10/2026 10:42:17.533")

    def test_rejects_a_frame_that_is_not_bgr(self) -> None:
        frame = np.zeros((20, 20), np.uint8)
        with self.assertRaises(ValueError):
            draw_timestamp(frame, "03/10/2026 10:42:17.533")


if __name__ == "__main__":
    unittest.main()
