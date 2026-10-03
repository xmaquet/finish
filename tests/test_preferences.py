import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from preferences import default_preferences, load_preferences, save_preferences, Preferences


class PreferencesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="finish-prefs-"))
        self.addCleanup(self._cleanup)
        self.path = self.root / "preferences.json"

    def test_missing_file_uses_the_validated_defaults(self) -> None:
        prefs = load_preferences(self.path)
        self.assertEqual(prefs, default_preferences())
        self.assertEqual((prefs.width, prefs.height, prefs.fps, prefs.buffer_seconds, prefs.jpeg_quality), (1920, 1080, 30, 30, 80))

    def test_invalid_file_uses_the_defaults(self) -> None:
        self.path.write_text("{", encoding="utf-8")
        prefs = load_preferences(self.path)
        self.assertEqual(prefs.fps, 30)
        self.assertEqual(prefs.width, 1920)
        self.path.write_text("[]", encoding="utf-8")
        self.assertEqual(load_preferences(self.path).jpeg_quality, 80)

    def test_a_rejected_value_falls_back_without_blocking(self) -> None:
        self.path.write_text(json.dumps({"fps": 12, "camera_index": 2, "place": "Stade"}), encoding="utf-8")
        prefs = load_preferences(self.path)
        self.assertEqual(prefs.fps, 30)
        self.assertEqual(prefs.camera_index, 2)
        self.assertEqual(prefs.place, "Stade")

    def test_round_trip_does_not_store_a_course_name(self) -> None:
        save_preferences(
            self.path,
            Preferences(camera_index=1, width=1280, height=720, fps=25, buffer_seconds=20, jpeg_quality=60, recordings_dir="D:/courses", place="Stade"),
        )
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertNotIn("course_name", raw)
        loaded = load_preferences(self.path)
        self.assertEqual(loaded.camera_index, 1)
        self.assertEqual((loaded.width, loaded.height), (1280, 720))
        self.assertEqual(loaded.recordings_dir, "D:/courses")
        self.assertEqual(loaded.place, "Stade")

    def _cleanup(self) -> None:
        if self.path.is_file():
            self.path.unlink()
        self.root.rmdir()
