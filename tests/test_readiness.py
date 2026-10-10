import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sessions.readiness import NAME_FIRST_ALERT, course_alerts, course_readiness


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

    def test_name_alert_hides_the_later_ones(self) -> None:
        folder = Path(tempfile.mkdtemp(prefix="finish-ready-"))
        self.addCleanup(folder.rmdir)
        missing = folder / "absent"
        alerts = course_alerts("  ", missing, 10, 1000, camera_available=False)
        self.assertEqual(alerts, [NAME_FIRST_ALERT])

    def test_later_alerts_appear_once_the_name_is_set(self) -> None:
        folder = Path(tempfile.mkdtemp(prefix="finish-ready-"))
        self.addCleanup(folder.rmdir)
        missing = folder / "absent"
        alerts = course_alerts("Cross", missing, 10, 1000, camera_available=False, detecting=True)
        self.assertEqual(
            alerts,
            [
                "Recherche des caméras…",
                "Le dossier d'enregistrement n'est pas accessible.",
            ],
        )
        alerts = course_alerts("Cross", folder, 10, 1000, camera_available=False)
        self.assertEqual(
            alerts,
            ["Aucune caméra détectée.", "Attention : espace disque faible."],
        )
        self.assertEqual(course_alerts("Cross", folder, 5000, 1000), [])


if __name__ == "__main__":
    unittest.main()
