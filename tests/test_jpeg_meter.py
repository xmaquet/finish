import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from video.jpeg_meter import JpegEncodeMeter


class JpegEncodeMeterTest(unittest.TestCase):
    def test_empty_meter(self) -> None:
        stats = JpegEncodeMeter().snapshot()
        self.assertEqual(stats.count, 0)
        self.assertEqual(stats.average_ms, 0.0)
        self.assertEqual(stats.average_bytes, 0)

    def test_average_min_and_max(self) -> None:
        meter = JpegEncodeMeter()
        meter.add_success(100, 4.0)
        meter.add_success(300, 8.0)
        meter.add_failure()
        stats = meter.snapshot()
        self.assertEqual(stats.count, 2)
        self.assertEqual(stats.failures, 1)
        self.assertEqual(stats.average_ms, 6.0)
        self.assertEqual(stats.min_ms, 4.0)
        self.assertEqual(stats.max_ms, 8.0)
        self.assertEqual(stats.average_bytes, 200)
        self.assertEqual(stats.min_bytes, 100)
        self.assertEqual(stats.max_bytes, 300)


if __name__ == "__main__":
    unittest.main()
