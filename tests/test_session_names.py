import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sessions.course import start_course
from sessions.names import (
    course_display_name,
    make_course_slug,
    recording_file_stem,
    recording_filenames,
)


class CourseNameTest(unittest.TestCase):
    def test_slug_keeps_the_typed_name_intact(self) -> None:
        self.assertEqual(make_course_slug("Course CM2 filles"), "course-cm2-filles")
        self.assertEqual(course_display_name("Course CM2 filles"), "Course CM2 filles")

    def test_cross_school_example(self) -> None:
        self.assertEqual(course_display_name("Cross école 2026"), "Cross école 2026")
        self.assertEqual(make_course_slug("Cross école 2026"), "cross-ecole-2026")

    def test_apostrophe_and_accent_stay_on_screen(self) -> None:
        raw = "Course d'été CE1"
        self.assertEqual(course_display_name(raw), raw)
        self.assertEqual(make_course_slug(raw), "course-dete-ce1")

    def test_spaces_punctuation_and_case(self) -> None:
        self.assertEqual(make_course_slug("  Cross   école   primaire  "), "cross-ecole-primaire")
        self.assertEqual(course_display_name("  Cross   école   primaire  "), "Cross   école   primaire")

    def test_windows_forbidden_characters_leave_the_slug(self) -> None:
        raw = 'Finale <filles> : "CM2" / \\ | ? *'
        slug = make_course_slug(raw)
        for character in '<>:"/\\|?*':
            self.assertNotIn(character, slug)
        self.assertEqual(slug, "finale-filles-cm2")
        self.assertEqual(course_display_name(raw), raw)

    def test_empty_name_defaults_to_course(self) -> None:
        self.assertEqual(course_display_name(None), "Course")
        self.assertEqual(course_display_name("   "), "Course")
        self.assertEqual(make_course_slug(""), "course")
        self.assertEqual(make_course_slug(None), "course")

    def test_symbols_only_fall_back_to_a_safe_slug(self) -> None:
        self.assertEqual(course_display_name("<<<>>>"), "<<<>>>")
        self.assertEqual(make_course_slug("<<<>>>"), "session")

    def test_long_name_is_truncated_without_a_trailing_hyphen(self) -> None:
        raw = "Course " + ("enfants " * 30)
        slug = make_course_slug(raw)
        self.assertLessEqual(len(slug), 48)
        self.assertFalse(slug.endswith("-"))
        self.assertTrue(slug.startswith("course-enfants"))

    def test_three_sessions_of_the_same_course(self) -> None:
        course = start_course("Cross école 2026")
        stamps = (
            datetime(2026, 10, 3, 10, 2, 15),
            datetime(2026, 10, 3, 10, 45, 2),
            datetime(2026, 10, 3, 11, 30, 18),
        )
        names = [
            recording_file_stem(stamp, course.course_name, course.allocate_session_id())
            for stamp in stamps
        ]
        self.assertEqual(
            names,
            [
                "2026-10-03_10-02-15_cross-ecole-2026_session-001",
                "2026-10-03_10-45-02_cross-ecole-2026_session-002",
                "2026-10-03_11-30-18_cross-ecole-2026_session-003",
            ],
        )
        video, metadata = recording_filenames(stamps[0], course.course_name, 1)
        self.assertEqual(video, "2026-10-03_10-02-15_cross-ecole-2026_session-001.mp4")
        self.assertEqual(metadata, "2026-10-03_10-02-15_cross-ecole-2026_session-001.json")

    def test_course_name_is_not_the_technical_id(self) -> None:
        course = start_course("Cross école 2026")
        first = course.open_session()
        second = course.open_session()
        self.assertEqual(first.course_name, "Cross école 2026")
        self.assertEqual(first.course_slug, "cross-ecole-2026")
        self.assertEqual(first.session_id, 1)
        self.assertEqual(second.session_id, 2)
        self.assertNotEqual(first.course_name, str(first.session_id))

    def test_a_new_course_restarts_session_numbers(self) -> None:
        first = start_course("Cross école 2026")
        first.allocate_session_id()
        second = start_course("Course CP")
        self.assertEqual(second.course_name, "Course CP")
        self.assertEqual(second.course_slug, "course-cp")
        self.assertEqual(second.allocate_session_id(), 1)


if __name__ == "__main__":
    unittest.main()
