import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from video.ring_buffer import BufferedFrame, RingBuffer


def _frame(second: float, payload: bytes | None = None) -> BufferedFrame:
    data = payload if payload is not None else f"{second:.3f}".encode("ascii")
    return BufferedFrame(
        monotonic_timestamp=second,
        wall_clock_timestamp=datetime(2026, 10, 3, 14, 32, 8) + timedelta(seconds=second),
        jpeg_data=data,
    )


class RingBufferTest(unittest.TestCase):
    def test_empty_snapshot_and_stats(self) -> None:
        buffer = RingBuffer(30)
        self.assertEqual(buffer.snapshot_last_seconds(10), [])
        stats = buffer.stats()
        self.assertEqual(stats.frame_count, 0)
        self.assertEqual(stats.duration_seconds, 0.0)
        self.assertEqual(stats.memory_bytes, 0)

    def test_appends_in_chronological_order(self) -> None:
        buffer = RingBuffer(30)
        for second in (0.0, 0.5, 1.0):
            buffer.append(_frame(second))
        times = [frame.monotonic_timestamp for frame in buffer.snapshot_last_seconds(30)]
        self.assertEqual(times, [0.0, 0.5, 1.0])

    def test_timestamps_stay_monotonic(self) -> None:
        buffer = RingBuffer(30)
        for second in range(12):
            buffer.append(_frame(float(second)))
        times = [frame.monotonic_timestamp for frame in buffer.snapshot_last_seconds(30)]
        self.assertEqual(times, sorted(times))
        self.assertEqual(times, list(range(12)))

    def test_purges_frames_older_than_the_window(self) -> None:
        buffer = RingBuffer(30)
        for second in range(0, 41):
            buffer.append(_frame(float(second), payload=bytes([second])))
        kept = [frame.monotonic_timestamp for frame in buffer.snapshot_last_seconds(30)]
        self.assertNotIn(0.0, kept)
        self.assertNotIn(9.0, kept)
        self.assertEqual(kept[0], 10.0)
        self.assertEqual(kept[-1], 40.0)
        self.assertLessEqual(kept[-1] - kept[0], 30.0)
        self.assertEqual(buffer.stats().memory_bytes, sum(len(frame.jpeg_data) for frame in buffer.snapshot_last_seconds(30)))

    def test_keeps_a_frame_aged_exactly_thirty_seconds(self) -> None:
        buffer = RingBuffer(30)
        buffer.append(_frame(10.0, payload=b"keep"))
        buffer.append(_frame(40.0, payload=b"now"))
        kept = [frame.jpeg_data for frame in buffer.snapshot_last_seconds(30)]
        self.assertEqual(kept, [b"keep", b"now"])
        self.assertEqual(buffer.stats().duration_seconds, 30.0)

    def test_purge_follows_time_not_frame_count(self) -> None:
        buffer = RingBuffer(30)
        buffer.append(_frame(0.0, payload=b"old"))
        buffer.append(_frame(10.0, payload=b"mid"))
        buffer.append(_frame(40.1, payload=b"new"))
        kept = [frame.jpeg_data for frame in buffer.snapshot_last_seconds(30)]
        self.assertEqual(kept, [b"new"])

    def test_snapshots_of_10_20_and_30_seconds(self) -> None:
        buffer = RingBuffer(30)
        for second in range(0, 41):
            buffer.append(_frame(float(second)))
        self.assertEqual(
            [frame.monotonic_timestamp for frame in buffer.snapshot_last_seconds(10)],
            [float(second) for second in range(30, 41)],
        )
        self.assertEqual(
            [frame.monotonic_timestamp for frame in buffer.snapshot_last_seconds(20)],
            [float(second) for second in range(20, 41)],
        )
        self.assertEqual(
            [frame.monotonic_timestamp for frame in buffer.snapshot_last_seconds(30)],
            [float(second) for second in range(10, 41)],
        )

    def test_request_longer_than_available_returns_everything(self) -> None:
        buffer = RingBuffer(30)
        for second in range(6):
            buffer.append(_frame(float(second)))
        snapshot = buffer.snapshot_last_seconds(30)
        self.assertEqual(len(snapshot), 6)
        self.assertEqual(snapshot[0].monotonic_timestamp, 0.0)
        self.assertEqual(snapshot[-1].monotonic_timestamp, 5.0)

    def test_snapshot_is_independent_of_later_updates(self) -> None:
        buffer = RingBuffer(30)
        for second in range(5):
            buffer.append(_frame(float(second), payload=f"f{second}".encode("ascii")))
        snapshot = buffer.snapshot_last_seconds(30)
        original = [frame.jpeg_data for frame in snapshot]
        buffer.append(_frame(100.0, payload=b"later"))
        self.assertEqual([frame.jpeg_data for frame in snapshot], original)
        self.assertEqual(buffer.stats().frame_count, 1)
        self.assertEqual(buffer.snapshot_last_seconds(30)[0].jpeg_data, b"later")
        snapshot.pop()
        self.assertEqual(buffer.stats().frame_count, 1)

    def test_rejects_a_non_positive_duration(self) -> None:
        buffer = RingBuffer(30)
        with self.assertRaises(ValueError):
            buffer.snapshot_last_seconds(0)
        with self.assertRaises(ValueError):
            RingBuffer(0)

    def test_snapshot_reuses_the_same_jpeg_bytes(self) -> None:
        buffer = RingBuffer(30)
        buffer.append(_frame(0.0, payload=b"abc"))
        buffer.append(_frame(1.0, payload=b"def"))
        first = buffer.snapshot_last_seconds(30)
        second = buffer.snapshot_last_seconds(30)
        self.assertIs(first[0].jpeg_data, second[0].jpeg_data)
        self.assertIsNot(first, second)

    def test_rejects_mutable_jpeg_storage(self) -> None:
        buffer = RingBuffer(30)
        frame = BufferedFrame(
            monotonic_timestamp=1.0,
            wall_clock_timestamp=datetime(2026, 10, 3, 14, 32, 8),
            jpeg_data=bytearray(b"mutable"),  # type: ignore[arg-type]
        )
        with self.assertRaises(TypeError):
            buffer.append(frame)


if __name__ == "__main__":
    unittest.main()
