"""Courses reconstruites à partir des sessions déjà enregistrées.

Les fichiers restent à plat dans recordings/. Aucune base, aucun déplacement.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from disk_space import format_byte_size
from sessions.catalog import RecordedSession


@dataclass(frozen=True)
class CourseArchive:
    """Une course et ses sessions, de la plus ancienne à la plus récente."""

    course_name: str
    course_slug: str
    sessions: tuple[RecordedSession, ...]

    @property
    def session_count(self) -> int:
        return len(self.sessions)

    @property
    def start_time(self) -> datetime:
        return self.sessions[0].start_time

    @property
    def end_time(self) -> datetime:
        return self.sessions[-1].end_time

    @property
    def date(self) -> datetime:
        return self.start_time

    @property
    def duration_total(self) -> float:
        return sum(session.duration_seconds for session in self.sessions)

    def size_total(self) -> int:
        return sum(session_size(session) for session in self.sessions)

    def index_of(self, session: RecordedSession) -> int:
        for index, item in enumerate(self.sessions):
            if item.video_path == session.video_path:
                return index
        return -1

    def previous_session(self, session: RecordedSession) -> RecordedSession | None:
        index = self.index_of(session)
        if index <= 0:
            return None
        return self.sessions[index - 1]

    def next_session(self, session: RecordedSession) -> RecordedSession | None:
        index = self.index_of(session)
        if index < 0 or index + 1 >= len(self.sessions):
            return None
        return self.sessions[index + 1]


def session_size(session: RecordedSession) -> int:
    total = 0
    if session.video_path.is_file():
        total += session.video_path.stat().st_size
    if session.metadata_path.is_file():
        total += session.metadata_path.stat().st_size
    return total


def build_courses(sessions: list[RecordedSession]) -> list[CourseArchive]:
    """La course la plus récente d'abord. Dans chaque course, l'ordre chronologique."""
    grouped: dict[str, list[RecordedSession]] = {}
    for session in sessions:
        grouped.setdefault(session.course_name, []).append(session)
    courses: list[CourseArchive] = []
    for name, items in grouped.items():
        ordered = tuple(sorted(items, key=lambda item: (item.start_time, item.session_id)))
        courses.append(
            CourseArchive(
                course_name=name,
                course_slug=ordered[0].course_slug,
                sessions=ordered,
            )
        )
    courses.sort(key=lambda course: course.end_time, reverse=True)
    return courses


def format_spoken_duration(seconds: float) -> str:
    """Durée lisible : 42 min 18 s, ou 1 h 02 min 03 s."""
    whole = max(0, int(seconds))
    minutes, secs = divmod(whole, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours} h {minutes:02d} min {secs:02d} s"
    return f"{minutes} min {secs:02d} s"


def format_summary(name: str, session_count: int, duration_seconds: float, size_bytes: int) -> str:
    label = "session" if session_count == 1 else "sessions"
    return (
        f"{name}\n"
        f"{session_count} {label}\n"
        f"{format_spoken_duration(duration_seconds)}\n"
        f"{format_byte_size(size_bytes)}"
    )


def format_course_summary(course: CourseArchive) -> str:
    return format_summary(
        course.course_name,
        course.session_count,
        course.duration_total,
        course.size_total(),
    )


def library_size(directory: Path) -> int:
    if not directory.is_dir():
        return 0
    total = 0
    for path in directory.iterdir():
        if path.is_file() and path.suffix.lower() in {".mp4", ".json"}:
            total += path.stat().st_size
    return total
