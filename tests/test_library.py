import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sessions.catalog import RecordedSession
from sessions.library import build_courses, format_summary


def _session(name: str, slug: str, number: int, hour: int, duration: float) -> RecordedSession:
    start = datetime(2026, 10, 3, hour, 0, 0)
    end = datetime(2026, 10, 3, hour, 1, 0)
    return RecordedSession(
        course_name=name,
        course_slug=slug,
        session_id=number,
        start_time=start,
        end_time=end,
        duration_seconds=duration,
        video_path=Path(f"{slug}-{number}.mp4"),
        metadata_path=Path(f"{slug}-{number}.json"),
        width=1920,
        height=1080,
        measured_fps=30,
        file_fps=30,
        frames_written=10,
        recording_dropped_frames=0,
        codec="mp4v",
        camera_index=0,
        backend="DSHOW",
        pixel_format="YUY2",
    )


class CourseLibraryTest(unittest.TestCase):
    def test_groups_by_course_and_keeps_chronological_order(self) -> None:
        courses = build_courses(
            [
                _session("Cross école 2026", "cross", 2, 11, 20),
                _session("Course CE1", "ce1", 1, 15, 5),
                _session("Cross école 2026", "cross", 1, 10, 10),
            ]
        )
        self.assertEqual([course.course_name for course in courses], ["Course CE1", "Cross école 2026"])
        cross = courses[1]
        self.assertEqual([item.session_id for item in cross.sessions], [1, 2])
        self.assertEqual(cross.session_count, 2)
        self.assertEqual(cross.duration_total, 30)
        self.assertEqual(cross.previous_session(cross.sessions[1]), cross.sessions[0])
        self.assertEqual(cross.next_session(cross.sessions[0]), cross.sessions[1])
        self.assertIsNone(cross.previous_session(cross.sessions[0]))
        self.assertIsNone(cross.next_session(cross.sessions[1]))

    def test_summary_is_readable(self) -> None:
        text = format_summary("Cross école 2026", 3, 42 * 60 + 18, int(3.6 * 1024**3))
        self.assertEqual(
            text,
            "Cross école 2026\n3 sessions\n42 min 18 s\n3,6 Go",
        )


if __name__ == "__main__":
    unittest.main()
