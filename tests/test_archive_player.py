import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from video.archive_player import (
    ArchivePlayer,
    frame_index_for_seconds,
    frame_index_for_wall_clock,
    locate_frame_for_clock_text,
    parse_clock_text,
    seconds_for_frame,
)


class FrameMappingTest(unittest.TestCase):
    def test_seconds_and_frames_meet_in_the_middle(self) -> None:
        self.assertEqual(frame_index_for_seconds(2.0, 30, 100), 60)
        self.assertEqual(frame_index_for_seconds(99, 30, 100), 99)
        self.assertAlmostEqual(seconds_for_frame(60, 30), 2.0)

    def test_wall_clock_uses_the_session_start(self) -> None:
        start = datetime(2026, 10, 3, 13, 24, 25)
        target = datetime(2026, 10, 3, 13, 25, 21)
        self.assertEqual(frame_index_for_wall_clock(start, target, 30, 4603), 56 * 30)


class ClockTextTest(unittest.TestCase):
    def test_accepts_seconds_and_milliseconds(self) -> None:
        self.assertEqual(parse_clock_text("13:25:21"), (13, 25, 21, 0))
        self.assertEqual(parse_clock_text(" 13:25:21.350 "), (13, 25, 21, 350))
        self.assertEqual(parse_clock_text("13:25:21.3"), (13, 25, 21, 300))
        self.assertIsNone(parse_clock_text("13:25"))
        self.assertIsNone(parse_clock_text("24:00:00"))

    def test_go_to_time_clamps_outside_the_session(self) -> None:
        start = datetime(2026, 10, 3, 13, 24, 25)
        inside = locate_frame_for_clock_text(start, "13:25:21", 30, 4603)
        self.assertEqual(inside, (56 * 30, "inside"))
        millis = locate_frame_for_clock_text(start, "13:25:21.350", 30, 4603)
        self.assertEqual(millis, (56 * 30 + 10, "inside"))
        self.assertEqual(
            locate_frame_for_clock_text(start, "13:00:00", 30, 4603),
            (0, "before"),
        )
        self.assertEqual(
            locate_frame_for_clock_text(start, "18:00:00", 30, 4603),
            (4602, "after"),
        )
        self.assertIsNone(locate_frame_for_clock_text(start, "midi", 30, 4603))


class ArchivePlayerTest(unittest.TestCase):
    def test_step_forward_and_back_shows_the_requested_frame(self) -> None:
        directory = Path(tempfile.mkdtemp(prefix="finish-play-"))
        self.addCleanup(lambda: _remove(directory))
        path = directory / "clip.mp4"
        _write_clip(path, 6)
        player = ArchivePlayer()
        self.addCleanup(player.close)
        self.assertTrue(player.open(path, file_fps=10))
        self.assertEqual(player.frame_index, 0)
        self.assertEqual(_marker(player.frame), 0)
        self.assertTrue(player.step(1))
        self.assertEqual(player.frame_index, 1)
        self.assertEqual(_marker(player.frame), 1)
        self.assertTrue(player.step(1))
        self.assertTrue(player.step(-1))
        self.assertEqual(player.frame_index, 1)
        self.assertEqual(_marker(player.frame), 1)
        self.assertTrue(player.seek(5))
        self.assertEqual(_marker(player.frame), 5)
        self.assertTrue(player.seek(0))
        self.assertEqual(_marker(player.frame), 0)
        self.assertFalse(player.step(-1) and player.frame_index != 0)
        self.assertEqual(player.frame_index, 0)


def _write_clip(path: Path, count: int) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (64, 48))
    for index in range(count):
        frame = np.zeros((48, 64, 3), dtype=np.uint8)
        frame[:, :] = (index * 30, 10, 20)
        writer.write(frame)
    writer.release()


def _marker(frame: np.ndarray | None) -> int:
    assert frame is not None
    return int(round(float(frame[0, 0, 0]) / 30))


def _remove(folder: Path) -> None:
    for path in folder.iterdir():
        path.unlink()
    folder.rmdir()


if __name__ == "__main__":
    unittest.main()
