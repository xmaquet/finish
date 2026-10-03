import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from camera.fourcc import fourcc_to_string


def _pack(text: str) -> int:
    value = 0
    for index, character in enumerate(text):
        value |= ord(character) << (8 * index)
    return value


class FourccTest(unittest.TestCase):
    def test_known_code(self) -> None:
        self.assertEqual(fourcc_to_string(_pack("MJPG")), "MJPG")

    def test_missing_code(self) -> None:
        self.assertEqual(fourcc_to_string(0), "n/a")
        self.assertEqual(fourcc_to_string(-1), "n/a")

    def test_unreadable_value(self) -> None:
        self.assertEqual(fourcc_to_string(float("nan")), "n/a")


if __name__ == "__main__":
    unittest.main()
