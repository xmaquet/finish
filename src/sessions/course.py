"""Une course active, et le prochain numéro de session en mémoire.

Une seule course est active à la fois. Le compteur en mémoire évite de
réutiliser un numéro avant que le fichier existe. Le numéro réellement
ouvert vient aussi des archives déjà présentes : voir sessions.archive.
"""

from __future__ import annotations

from dataclasses import dataclass

from sessions.names import course_display_name, format_session_id, make_course_slug


@dataclass(frozen=True)
class CourseSession:
    course_name: str
    course_slug: str
    session_id: int

    @property
    def session_id_label(self) -> str:
        return format_session_id(self.session_id)


@dataclass
class ActiveCourse:
    course_name: str
    course_slug: str
    _next_session_id: int = 1

    def next_session_floor(self) -> int:
        return self._next_session_id

    def note_opened_session(self, session_id: int) -> None:
        if session_id < 1:
            raise ValueError("session_id must be >= 1")
        self._next_session_id = max(self._next_session_id, session_id + 1)

    def allocate_session_id(self) -> int:
        session_id = self._next_session_id
        self._next_session_id += 1
        return session_id

    def open_session(self) -> CourseSession:
        return CourseSession(
            course_name=self.course_name,
            course_slug=self.course_slug,
            session_id=self.allocate_session_id(),
        )


def start_course(raw_name: str | None) -> ActiveCourse:
    name = course_display_name(raw_name)
    return ActiveCourse(course_name=name, course_slug=make_course_slug(name))
