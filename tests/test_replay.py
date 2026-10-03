import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from video.replay import ReplayPlayer
from video.ring_buffer import BufferedFrame, RingBuffer


def _frame(second: float, payload: bytes | None = None) -> BufferedFrame:
    data = payload if payload is not None else f"{second:.3f}".encode("ascii")
    return BufferedFrame(
        monotonic_timestamp=second,
        wall_clock_timestamp=datetime(2026, 10, 3, 11, 55, 0) + timedelta(seconds=second),
        jpeg_data=data,
    )


def _sequence(start: float, end: float, step: float = 1.0) -> list[BufferedFrame]:
    frames = []
    second = start
    while second <= end + 1e-9:
        frames.append(_frame(second))
        second += step
    return frames


class ReplayPlayerTest(unittest.TestCase):
    def test_replay_10_20_and_30_seconds(self) -> None:
        for requested in (10, 20, 30):
            frames = _sequence(0, requested)
            player = ReplayPlayer(frames, requested_seconds=requested)
            player.start(1000.0)
            self.assertEqual(player.frame_count, requested + 1)
            self.assertAlmostEqual(player.duration_seconds, requested)
            self.assertEqual(player.mode_label(), f"REPLAY — {requested} s")
            opening = player.advance(1000.0)
            self.assertEqual(opening.index, 0)
            self.assertFalse(opening.finished)
            middle = player.advance(1000.0 + requested / 2)
            self.assertEqual(middle.index, requested // 2)
            ending = player.advance(1000.0 + requested)
            self.assertEqual(ending.index, requested)
            self.assertFalse(ending.finished)
            done = player.advance(1000.0 + requested + 0.01)
            self.assertTrue(done.finished)

    def test_short_buffer_plays_what_is_available(self) -> None:
        frames = _sequence(0, 12)
        player = ReplayPlayer(frames, requested_seconds=30)
        self.assertEqual(player.frame_count, 13)
        self.assertAlmostEqual(player.duration_seconds, 12.0)
        self.assertEqual(player.mode_label(), "REPLAY — 12.0 s")
        player.start(0.0)
        self.assertFalse(player.advance(12.0).finished)
        self.assertTrue(player.advance(12.1).finished)

    def test_frames_stay_in_capture_order(self) -> None:
        frames = _sequence(0, 5)
        player = ReplayPlayer(frames, requested_seconds=10)
        player.start(0.0)
        indexes = [player.advance(float(second)).index for second in range(6)]
        self.assertEqual(indexes, [0, 1, 2, 3, 4, 5])

    def test_pause_holds_the_frame_and_resume_continues(self) -> None:
        player = ReplayPlayer(_sequence(0, 10), requested_seconds=10)
        player.start(0.0)
        self.assertEqual(player.advance(3.0).index, 3)
        player.pause()
        held = player.advance(8.0)
        self.assertTrue(held.paused)
        self.assertEqual(held.index, 3)
        self.assertFalse(held.finished)
        player.resume(20.0)
        self.assertEqual(player.advance(21.0).index, 4)

    def test_step_moves_only_while_paused(self) -> None:
        player = ReplayPlayer(_sequence(0, 5), requested_seconds=10)
        player.start(0.0)
        player.advance(1.0)
        player.step(1)
        self.assertEqual(player.advance(1.0).index, 1)
        player.pause()
        player.step(1)
        self.assertEqual(player.advance(1.0).index, 2)
        player.step(-1)
        self.assertEqual(player.advance(1.0).index, 1)
        player.step(-10)
        self.assertEqual(player.advance(1.0).index, 0)
        player.step(50)
        self.assertEqual(player.advance(1.0).index, 5)

    def test_snapshot_bytes_are_shared_and_the_live_buffer_keeps_growing(self) -> None:
        buffer = RingBuffer(30)
        for second in range(6):
            buffer.append(_frame(float(second), payload=f"f{second}".encode("ascii")))
        snapshot = buffer.snapshot_last_seconds(10)
        self.assertIs(snapshot[0].jpeg_data, buffer.snapshot_last_seconds(10)[0].jpeg_data)
        player = ReplayPlayer(snapshot, requested_seconds=10)
        player.start(0.0)
        view = player.advance(0.0)
        self.assertIs(view.jpeg_data, snapshot[0].jpeg_data)
        buffer.append(_frame(7.0, payload=b"newer"))
        self.assertEqual(player.frame_count, 6)
        self.assertEqual(buffer.stats().frame_count, 7)
        self.assertEqual(snapshot[0].jpeg_data, b"f0")

    def test_empty_snapshot_finishes_immediately(self) -> None:
        player = ReplayPlayer([], requested_seconds=10)
        view = player.advance(0.0)
        self.assertTrue(view.finished)
        self.assertIsNone(view.jpeg_data)


if __name__ == "__main__":
    unittest.main()
