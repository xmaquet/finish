import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sessions.catalog import (
    RecordedSession,
    format_duration_minutes,
    group_sessions,
    scan_recordings,
    session_summary,
)
from sessions.metadata import SessionMetadata, write_metadata


def _metadata(video_name: str, session_id: int, start: str, course: str = "Cross école 2026") -> SessionMetadata:
    return SessionMetadata(
        course_name=course,
        course_slug="cross-ecole-2026",
        session_id=session_id,
        start_time=start,
        end_time="2026-10-03T13:26:58.504",
        duration_seconds=153.12,
        video_file=video_name,
        camera_index=0,
        backend="DSHOW",
        pixel_format="YUY2",
        width=64,
        height=48,
        requested_fps=30,
        measured_fps=30.2,
        file_fps=30,
        codec="mp4v",
        frames_written=6,
        recording_dropped_frames=0,
    )


def _write_video(path: Path) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (64, 48))
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    writer.write(frame)
    writer.release()


class CatalogTest(unittest.TestCase):
    def test_duration_and_summary_match_the_list(self) -> None:
        self.assertEqual(format_duration_minutes(153.12), "02:33")
        session = RecordedSession(
            course_name="Cross école 2026",
            course_slug="cross-ecole-2026",
            session_id=3,
            start_time=datetime(2026, 10, 3, 13, 24, 25),
            end_time=datetime(2026, 10, 3, 13, 26, 58),
            duration_seconds=153.12,
            video_path=Path("video.mp4"),
            metadata_path=Path("video.json"),
            width=1920,
            height=1080,
            measured_fps=30.2,
            file_fps=30,
            frames_written=4603,
            recording_dropped_frames=0,
            codec="mp4v",
            camera_index=0,
            backend="DSHOW",
            pixel_format="YUY2",
        )
        self.assertEqual(
            session_summary(session),
            "Cross école 2026 | 03/10/2026 | 13:24:25 | Session 003 | 02:33",
        )

    def test_groups_keep_a_course_together_with_the_newest_first(self) -> None:
        school = _session("Cross école 2026", 1, datetime(2026, 10, 3, 10, 0, 0))
        later = _session("Cross école 2026", 3, datetime(2026, 10, 3, 13, 24, 25))
        other = _session("Course CP", 1, datetime(2026, 10, 3, 11, 0, 0))
        groups = group_sessions([school, other, later])
        self.assertEqual([name for name, _sessions in groups], ["Cross école 2026", "Course CP"])
        self.assertEqual([item.session_id for item in groups[0][1]], [3, 1])

    def test_scan_keeps_a_valid_pair_and_skips_broken_files(self) -> None:
        directory = Path(tempfile.mkdtemp(prefix="finish-cat-"))
        self.addCleanup(lambda: _remove(directory))
        stem = "2026-10-03_13-24-25_cross-ecole-2026_session-003"
        video = directory / f"{stem}.mp4"
        _write_video(video)
        write_metadata(directory / f"{stem}.json", _metadata(video.name, 3, "2026-10-03T13:24:25.384"))
        (directory / "2026-10-03_13-18-37_cross-ecole-2026_session-001.mp4").write_bytes(b"x")
        write_metadata(
            directory / "2026-10-03_13-21-07_cross-ecole-2026_session-002.json",
            _metadata("2026-10-03_13-21-07_cross-ecole-2026_session-002.mp4", 2, "2026-10-03T13:21:07"),
        )
        (directory / "2026-10-03_10-00-00_cross-ecole-2026_session-004.json").write_text("{", encoding="utf-8")
        (directory / "2026-10-03_10-00-00_cross-ecole-2026_session-004.mp4").write_bytes(b"not-a-video")
        bad_video = directory / "2026-10-03_11-00-00_cross-ecole-2026_session-005.mp4"
        bad_video.write_bytes(b"not-a-video")
        write_metadata(
            directory / "2026-10-03_11-00-00_cross-ecole-2026_session-005.json",
            _metadata(bad_video.name, 5, "2026-10-03T11:00:00"),
        )
        found = scan_recordings(directory)
        self.assertEqual([item.session_id for item in found], [3])
        self.assertEqual(found[0].course_name, "Cross école 2026")
        self.assertEqual(found[0].frames_written, 6)
        self.assertEqual(found[0].video_path.name, video.name)

    def test_course_name_comes_from_the_json(self) -> None:
        directory = Path(tempfile.mkdtemp(prefix="finish-cat-"))
        self.addCleanup(lambda: _remove(directory))
        stem = "2026-10-03_10-02-15_course-dete-cm2-filles_session-001"
        video = directory / f"{stem}.mp4"
        _write_video(video)
        write_metadata(
            directory / f"{stem}.json",
            _metadata(video.name, 1, "2026-10-03T10:02:15", course="Course d'été – CM2 filles"),
        )
        found = scan_recordings(directory)
        self.assertEqual(found[0].course_name, "Course d'été – CM2 filles")
        raw = json.loads((directory / f"{stem}.json").read_text(encoding="utf-8"))
        self.assertEqual(raw["course_name"], "Course d'été – CM2 filles")


def _session(name: str, session_id: int, start: datetime) -> RecordedSession:
    return RecordedSession(
        course_name=name,
        course_slug="slug",
        session_id=session_id,
        start_time=start,
        end_time=start,
        duration_seconds=10,
        video_path=Path("v.mp4"),
        metadata_path=Path("v.json"),
        width=1,
        height=1,
        measured_fps=30,
        file_fps=30,
        frames_written=1,
        recording_dropped_frames=0,
        codec="mp4v",
        camera_index=0,
        backend="",
        pixel_format="",
    )


def _remove(folder: Path) -> None:
    for path in folder.iterdir():
        path.unlink()
    folder.rmdir()


if __name__ == "__main__":
    unittest.main()
