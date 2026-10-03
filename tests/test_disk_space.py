import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from config import DISK_FREE_WARNING_BYTES
from disk_space import autonomy_minutes, disk_space_message, format_autonomy, format_free_space, free_bytes


class DiskSpaceTest(unittest.TestCase):
    def test_formats_gigabytes_and_megabytes(self) -> None:
        self.assertEqual(format_free_space(82 * 1024**3), "82 Go")
        self.assertEqual(format_free_space(int(9.4 * 1024**3)), "9,4 Go")
        self.assertEqual(format_free_space(512 * 1024**2), "512 Mo")

    def test_warning_is_below_the_threshold_only(self) -> None:
        self.assertEqual(DISK_FREE_WARNING_BYTES, 10 * 1024**3)
        text, low = disk_space_message(82 * 1024**3, DISK_FREE_WARNING_BYTES)
        self.assertFalse(low)
        self.assertEqual(text, "Espace disponible : 82 Go")
        text, low = disk_space_message(9 * 1024**3, DISK_FREE_WARNING_BYTES)
        self.assertTrue(low)
        self.assertIn("attention", text)

    def test_estimates_autonomy_from_the_observed_rate(self) -> None:
        free = 20 * 1024**3
        self.assertEqual(autonomy_minutes(free), (20 * 1024) // 131)
        self.assertEqual(format_autonomy(free), "environ 2 h 36")
        self.assertEqual(format_autonomy(0), "environ 0 min")

    def test_reads_the_disk_that_holds_the_folder(self) -> None:
        folder = Path(tempfile.mkdtemp(prefix="finish-disk-"))
        self.addCleanup(folder.rmdir)
        self.assertGreater(free_bytes(folder), 0)


if __name__ == "__main__":
    unittest.main()
