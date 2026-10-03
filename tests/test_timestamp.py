import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from camera.timestamp import format_timestamp


class TimestampFormatTest(unittest.TestCase):
    def test_example_from_the_brief(self) -> None:
        moment = datetime(2026, 10, 3, 10, 42, 17, 533000)
        self.assertEqual(format_timestamp(moment), "03/10/2026 10:42:17.533")

    def test_truncates_microseconds_instead_of_rounding(self) -> None:
        moment = datetime(2026, 10, 3, 10, 42, 17, 533999)
        self.assertEqual(format_timestamp(moment), "03/10/2026 10:42:17.533")

    def test_pads_date_and_zero_milliseconds(self) -> None:
        moment = datetime(2026, 1, 2, 3, 4, 5, 6)
        self.assertEqual(format_timestamp(moment), "02/01/2026 03:04:05.000")


if __name__ == "__main__":
    unittest.main()
