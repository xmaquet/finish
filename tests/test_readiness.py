import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sessions.readiness import course_readiness


class ReadinessTest(unittest.TestCase):
    def test_blocks_without_a_name_or_a_folder(self) -> None:
        folder = Path(tempfile.mkdtemp(prefix="finish-ready-"))
        self.addCleanup(folder.rmdir)
        self.assertFalse(course_readiness("  ", folder, 10**12, 1).allowed)
        missing = folder / "absent"
        self.assertFalse(course_readiness("Cross", missing, 10**12, 1).allowed)
        self.assertEqual(course_readiness("Cross", folder, 10**12, 1, camera_available=False).detail, "Aucune caméra détectée.")

    def test_warns_without_blocking_when_disk_space_is_low(self) -> None:
        folder = Path(tempfile.mkdtemp(prefix="finish-ready-"))
        self.addCleanup(folder.rmdir)
        ready = course_readiness("Cross", folder, 100, 1000)
        self.assertTrue(ready.allowed)
        self.assertEqual(ready.headline, "À vérifier")
        self.assertIn("espace disque faible", ready.detail)
        ready = course_readiness("Cross", folder, 5000, 1000)
        self.assertTrue(ready.allowed)
        self.assertEqual(ready.headline, "Prêt")


if __name__ == "__main__":
    unittest.main()
