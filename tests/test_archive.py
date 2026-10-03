import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sessions.archive import next_session_id, reserve_new_session, session_ids_for_slug
from sessions.course import start_course


class ArchiveTest(unittest.TestCase):
    def test_empty_directory_starts_at_one(self) -> None:
        directory = Path(self._tmp())
        self.assertEqual(next_session_id(directory, "cross-ecole-2026"), 1)

    def test_next_id_follows_the_highest_archive_for_that_course(self) -> None:
        directory = self._tmp()
        for number in (1, 2, 3):
            self._touch(directory, "cross-ecole-2026", number, day=1)
        self._touch(directory, "course-cp", 1, day=2)
        self.assertEqual(session_ids_for_slug(directory, "cross-ecole-2026"), {1, 2, 3})
        self.assertEqual(next_session_id(directory, "cross-ecole-2026"), 4)
        self.assertEqual(next_session_id(directory, "course-cp"), 2)

    def test_a_gap_does_not_reuse_an_old_number(self) -> None:
        directory = self._tmp()
        self._touch(directory, "cross-ecole-2026", 1, day=1)
        self._touch(directory, "cross-ecole-2026", 3, day=1)
        self.assertEqual(next_session_id(directory, "cross-ecole-2026"), 4)

    def test_reserve_never_returns_an_existing_path(self) -> None:
        directory = self._tmp()
        for number in (1, 2, 3):
            self._touch(directory, "cross-ecole-2026", number, day=1)
        start = datetime(2026, 10, 3, 14, 32, 8)
        planted = directory / "2026-10-03_14-32-08_cross-ecole-2026_session-004.mp4"
        planted.write_bytes(b"already")
        reserved = reserve_new_session(
            directory,
            "Cross école 2026",
            "cross-ecole-2026",
            start,
        )
        self.assertEqual(reserved.session_id, 5)
        self.assertEqual(reserved.session_id_label, "005")
        self.assertFalse(reserved.video_path.exists())
        self.assertFalse(reserved.metadata_path.exists())
        self.assertEqual(reserved.video_path.stem, reserved.metadata_path.stem)
        self.assertTrue(reserved.video_path.name.endswith(".mp4"))
        self.assertTrue(reserved.metadata_path.name.endswith(".json"))

    def test_memory_floor_and_disk_both_count(self) -> None:
        directory = self._tmp()
        self._touch(directory, "cross-ecole-2026", 2, day=4)
        course = start_course("Cross école 2026")
        course.note_opened_session(3)
        reserved = reserve_new_session(
            directory,
            course.course_name,
            course.course_slug,
            datetime(2026, 10, 3, 11, 0, 0),
            minimum_id=course.next_session_floor(),
        )
        self.assertEqual(reserved.session_id, 4)
        course.note_opened_session(reserved.session_id)
        self.assertEqual(course.next_session_floor(), 5)

    def test_same_slug_on_another_date_still_avoids_overwrite(self) -> None:
        directory = self._tmp()
        self._touch(directory, "cross-ecole", 1, day=1, year=2026)
        reserved = reserve_new_session(
            directory,
            "Cross école",
            "cross-ecole",
            datetime(2027, 10, 3, 10, 0, 0),
        )
        self.assertEqual(reserved.session_id, 2)
        self.assertIn("2027-10-03_10-00-00_cross-ecole_session-002", reserved.video_path.name)

    def _tmp(self) -> Path:
        directory = Path(self.id().replace(".", "_"))
        # unittest does not give tmp_path. Use a folder under the system temp via Path in the test method.
        import tempfile

        folder = Path(tempfile.mkdtemp(prefix="finish-archive-"))
        self.addCleanup(lambda: self._remove(folder))
        return folder

    def _touch(self, directory: Path, slug: str, number: int, day: int, year: int = 2026) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        name = f"{year}-10-{day:02d}_08-00-00_{slug}_session-{number:03d}.mp4"
        (directory / name).write_bytes(b"x")

    def _remove(self, folder: Path) -> None:
        for path in folder.iterdir():
            path.unlink()
        folder.rmdir()


if __name__ == "__main__":
    unittest.main()
