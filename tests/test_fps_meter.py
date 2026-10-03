import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from camera.fps_meter import FpsMeter


class FpsMeterTest(unittest.TestCase):
    def test_needs_two_samples(self) -> None:
        meter = FpsMeter(1.0)
        self.assertEqual(meter.tick(0.0), 0.0)
        self.assertFalse(meter.ready)

    def test_rate_over_a_full_window(self) -> None:
        meter = FpsMeter(1.0)
        for index in range(11):
            meter.tick(index * 0.1)
        self.assertAlmostEqual(meter.value, 10.0)
        self.assertTrue(meter.ready)

    def test_not_ready_before_the_window_is_covered(self) -> None:
        meter = FpsMeter(1.0)
        meter.tick(0.0)
        meter.tick(0.5)
        self.assertAlmostEqual(meter.value, 2.0)
        self.assertFalse(meter.ready)

    def test_drops_samples_older_than_the_window(self) -> None:
        meter = FpsMeter(1.0)
        meter.tick(0.0)
        meter.tick(0.4)
        self.assertEqual(meter.tick(1.5), 0.0)
        self.assertAlmostEqual(meter.tick(2.0), 2.0)

    def test_zero_span_is_not_a_rate(self) -> None:
        meter = FpsMeter(1.0)
        meter.tick(1.0)
        self.assertEqual(meter.tick(1.0), 0.0)
        self.assertFalse(meter.ready)

    def test_reset(self) -> None:
        meter = FpsMeter(1.0)
        meter.tick(0.0)
        meter.tick(1.0)
        meter.reset()
        self.assertEqual(meter.value, 0.0)
        self.assertFalse(meter.ready)

    def test_rejects_non_positive_window(self) -> None:
        with self.assertRaises(ValueError):
            FpsMeter(0)


if __name__ == "__main__":
    unittest.main()
