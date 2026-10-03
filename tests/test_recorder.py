import sys
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sessions.archive import reserve_new_session
from sessions.metadata import read_metadata
from video.recorder import RecorderError, RecordingQueue, SessionRecorder, file_frame_rate


class FileFrameRateTest(unittest.TestCase):
    def test_keeps_the_requested_rate_when_the_camera_is_close(self) -> None:
        self.assertEqual(file_frame_rate(29.76, True, 30), 30.0)

    def test_uses_the_measured_rate_when_the_camera_is_far_from_the_request(self) -> None:
        self.assertEqual(file_frame_rate(15.24, True, 30), 15.24)

    def test_falls_back_to_the_requested_rate(self) -> None:
        self.assertEqual(file_frame_rate(0.0, False, 30), 30.0)


class RecordingQueueTest(unittest.TestCase):
    def test_a_full_queue_drops_the_new_frame_and_counts_it(self) -> None:
        items = RecordingQueue(max_frames=2)
        frame = np.zeros((4, 4, 3), dtype=np.uint8)
        self.assertTrue(items.offer(frame))
        self.assertTrue(items.offer(frame))
        self.assertFalse(items.offer(frame))
        self.assertFalse(items.offer(frame))
        self.assertEqual(items.dropped_frames, 2)

    def test_close_rejects_new_frames_without_counting_a_drop(self) -> None:
        items = RecordingQueue(max_frames=2)
        frame = np.zeros((4, 4, 3), dtype=np.uint8)
        items.close()
        self.assertFalse(items.offer(frame))
        self.assertEqual(items.dropped_frames, 0)
        self.assertFalse(items.accepting)


class SessionRecorderTest(unittest.TestCase):
    def test_writes_mp4_and_final_metadata_without_dropping_frames(self) -> None:
        directory = Path(tempfile.mkdtemp(prefix="finish-rec-"))
        self.addCleanup(lambda: self._remove(directory))
        course_name = "Course d'été – CM2 filles"
        reserved = reserve_new_session(
            directory,
            course_name,
            "course-dete-cm2-filles",
            datetime(2026, 10, 3, 14, 32, 8),
        )
        recorder = SessionRecorder(
            reserved,
            course_name=course_name,
            course_slug="course-dete-cm2-filles",
            width=320,
            height=240,
            file_fps=10,
            camera_index=0,
            backend="DSHOW",
            pixel_format="YUY2",
            requested_fps=30,
            measured_fps=29.8,
            max_frames=8,
        )
        self.assertEqual(recorder.state, "idle")
        recorder.start()
        self.assertEqual(recorder.state, "recording")
        for index in range(6):
            frame = np.full((240, 320, 3), index * 20, dtype=np.uint8)
            self.assertTrue(recorder.offer(frame))
        time.sleep(0.02)
        metadata = recorder.stop(timeout=5)
        self.assertEqual(recorder.state, "stopped")
        self.assertIsNotNone(metadata)
        assert metadata is not None
        self.assertEqual(metadata.frames_written, 6)
        self.assertEqual(metadata.recording_dropped_frames, 0)
        self.assertEqual(metadata.course_name, course_name)
        self.assertEqual(metadata.codec, "mp4v")
        self.assertEqual(metadata.session_id, 1)
        self.assertEqual(metadata.video_file, reserved.video_path.name)
        self.assertEqual(reserved.video_path.stem, reserved.metadata_path.stem)
        self.assertGreater(metadata.duration_seconds, 0)
        stored = read_metadata(reserved.metadata_path)
        self.assertEqual(stored, metadata)
        self.assertFalse(recorder.offer(np.zeros((240, 320, 3), dtype=np.uint8)))
        self.assertEqual(recorder.dropped_frames, 0)

        capture = cv2.VideoCapture(str(reserved.video_path))
        self.addCleanup(capture.release)
        read_back = 0
        while True:
            ok, _frame = capture.read()
            if not ok:
                break
            read_back += 1
        self.assertEqual(read_back, 6)

    def test_refuses_to_open_an_existing_file(self) -> None:
        directory = Path(tempfile.mkdtemp(prefix="finish-rec-"))
        self.addCleanup(lambda: self._remove(directory))
        reserved = reserve_new_session(
            directory,
            "Cross école 2026",
            "cross-ecole-2026",
            datetime(2026, 10, 3, 10, 0, 0),
        )
        reserved.video_path.write_bytes(b"keep")
        with self.assertRaises(RecorderError):
            SessionRecorder(
                reserved,
                course_name="Cross école 2026",
                course_slug="cross-ecole-2026",
                width=320,
                height=240,
                file_fps=25,
                camera_index=0,
                backend="DSHOW",
                pixel_format="YUY2",
                requested_fps=30,
                measured_fps=30,
            )
        self.assertEqual(reserved.video_path.read_bytes(), b"keep")

    def _remove(self, folder: Path) -> None:
        for path in folder.iterdir():
            path.unlink()
        folder.rmdir()
