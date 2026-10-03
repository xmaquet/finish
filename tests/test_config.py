import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from config import (
    CAMERA_INDEX,
    DEFAULT_COURSE_NAME,
    JPEG_QUALITY,
    LOGO_PATH,
    RECORDING_CODEC,
    RECORDING_QUEUE_MAX_FRAMES,
    MAX_BUFFER_SECONDS,
    RECORDINGS_DIR,
    REQUESTED_FPS,
    REQUESTED_HEIGHT,
    REQUESTED_WIDTH,
)


class ConfigTest(unittest.TestCase):
    def test_defaults_match_the_brief(self) -> None:
        self.assertEqual(CAMERA_INDEX, 0)
        self.assertEqual(MAX_BUFFER_SECONDS, 30)
        self.assertEqual(REQUESTED_WIDTH, 1920)
        self.assertEqual(REQUESTED_HEIGHT, 1080)
        self.assertEqual(REQUESTED_FPS, 30)
        self.assertEqual(JPEG_QUALITY, 80)
        self.assertEqual(DEFAULT_COURSE_NAME, "Course")
        self.assertEqual(RECORDING_CODEC, "mp4v")
        self.assertEqual(RECORDING_QUEUE_MAX_FRAMES, 30)

    def test_recordings_directory_is_anchored_to_the_project(self) -> None:
        self.assertTrue(RECORDINGS_DIR.is_absolute())
        self.assertEqual(RECORDINGS_DIR.name, "recordings")
        self.assertTrue(LOGO_PATH.is_absolute())
        self.assertEqual(LOGO_PATH.name, "finish.png")


if __name__ == "__main__":
    unittest.main()
