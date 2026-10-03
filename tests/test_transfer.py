import json
import sys
import tempfile
import threading
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sessions.catalog import RecordedSession
from sessions.library import CourseArchive
from sessions.metadata import SessionMetadata, write_metadata
from version import VERSION
from sessions.transfer import (
    delete_local_files,
    export_course,
    export_folder_name,
    export_session,
    may_remove_sources,
)


def _metadata(video_name: str, number: int) -> SessionMetadata:
    return SessionMetadata(
        course_name="Cross école 2026",
        course_slug="cross-ecole-2026",
        session_id=number,
        start_time="2026-10-03T10:00:00",
        end_time="2026-10-03T10:01:00",
        duration_seconds=60,
        video_file=video_name,
        camera_index=0,
        backend="DSHOW",
        pixel_format="YUY2",
        width=64,
        height=48,
        requested_fps=30,
        measured_fps=30,
        file_fps=30,
        codec="mp4v",
        frames_written=3,
        recording_dropped_frames=0,
    )


class ExportTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="finish-export-"))
        self.addCleanup(self._cleanup)
        self.source = self.root / "src"
        self.dest = self.root / "dest"
        self.source.mkdir()
        self.dest.mkdir()
        self.video = self.source / "prise.mp4"
        self.meta = self.source / "prise.json"
        self.video.write_bytes(b"video-bytes")
        write_metadata(self.meta, _metadata(self.video.name, 1))

    def test_copies_a_session_and_leaves_the_original(self) -> None:
        result = export_session(self.video, self.meta, self.dest, include_json=True, free=10_000)
        self.assertTrue(result.succeeded)
        self.assertTrue(may_remove_sources(result))
        self.assertEqual((self.dest / "prise.mp4").read_bytes(), b"video-bytes")
        self.assertEqual((self.dest / "prise.mp4").stat().st_size, self.video.stat().st_size)
        self.assertTrue(self.video.is_file())

    def test_refuses_a_missing_folder_a_conflict_and_a_full_disk(self) -> None:
        missing = export_session(self.video, self.meta, self.root / "absent", include_json=True)
        self.assertEqual(missing.status, "missing_destination")
        (self.dest / "prise.mp4").write_bytes(b"keep")
        conflict = export_session(self.video, self.meta, self.dest, include_json=False, free=10_000)
        self.assertEqual(conflict.status, "conflict")
        self.assertEqual((self.dest / "prise.mp4").read_bytes(), b"keep")
        tight = export_session(self.video, None, self.dest / "autre", include_json=False, free=1)
        (self.dest / "autre").mkdir()
        tight = export_session(self.video, None, self.dest / "autre", include_json=False, free=1)
        self.assertEqual(tight.status, "insufficient_space")
        self.assertTrue(self.video.is_file())

    def test_cancel_does_not_authorize_deletion(self) -> None:
        cancel = threading.Event()
        cancel.set()
        result = export_session(self.video, self.meta, self.dest, include_json=True, free=10_000, cancel=cancel)
        self.assertEqual(result.status, "cancelled")
        self.assertFalse(may_remove_sources(result))
        self.assertTrue(self.video.is_file())

    def test_course_export_renames_sessions_and_writes_a_manifest(self) -> None:
        session = RecordedSession(
            course_name="Cross école 2026",
            course_slug="cross-ecole-2026",
            session_id=1,
            start_time=datetime(2026, 10, 3, 10, 0, 0),
            end_time=datetime(2026, 10, 3, 10, 1, 0),
            duration_seconds=60,
            video_path=self.video,
            metadata_path=self.meta,
            width=64,
            height=48,
            measured_fps=30,
            file_fps=30,
            frames_written=3,
            recording_dropped_frames=0,
            codec="mp4v",
            camera_index=0,
            backend="DSHOW",
            pixel_format="YUY2",
        )
        course = CourseArchive("Cross école 2026", "cross-ecole-2026", (session,))
        result = export_course(course, self.dest, free=10_000_000)
        self.assertTrue(result.succeeded, result.message)
        folder = self.dest / export_folder_name(course.course_name)
        self.assertEqual((folder / "session-001.mp4").read_bytes(), b"video-bytes")
        copied = (folder / "session-001.json").read_text(encoding="utf-8")
        self.assertIn("session-001.mp4", copied)
        self.assertTrue((folder / "course.json").is_file())
        manifest = json.loads((folder / "course.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["finish_version"], VERSION)
        self.assertIn("T", manifest["export_time"])
        self.assertEqual((folder / "course.json").stat().st_size, len((folder / "course.json").read_bytes()))
        self.assertEqual(self.meta.read_text(encoding="utf-8").count("prise.mp4"), 1)

    def test_local_delete_is_explicit(self) -> None:
        freed = delete_local_files([self.video, self.meta])
        self.assertGreater(freed, 0)
        self.assertFalse(self.video.exists())
        self.assertFalse(self.meta.exists())

    def _cleanup(self) -> None:
        for path in sorted(self.root.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            else:
                path.rmdir()
        self.root.rmdir()


if __name__ == "__main__":
    unittest.main()
