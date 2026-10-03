"""Liste des courses, puis le détail de leurs sessions."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from disk_space import format_byte_size
from sessions.catalog import RecordedSession, format_duration_minutes
from sessions.library import CourseArchive


class CourseBrowser(QWidget):
    play_requested = Signal(object)
    export_session_requested = Signal(object)
    delete_session_requested = Signal(object)
    export_course_requested = Signal(object)
    delete_course_requested = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._courses: list[CourseArchive] = []
        self._course: CourseArchive | None = None

        self._list_page = QWidget()
        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(self._open_current)
        list_layout = QVBoxLayout(self._list_page)
        list_layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Courses")
        title.setObjectName("screenTitle")
        self._empty = QLabel("Aucune course enregistrée.")
        self._empty.setObjectName("muted")
        self._empty.hide()
        list_layout.addWidget(title)
        list_layout.addWidget(self._list, stretch=1)
        list_layout.addWidget(self._empty)
        open_button = QPushButton("Ouvrir la course")
        open_button.setObjectName("primary")
        open_button.clicked.connect(self._open_current)
        list_layout.addWidget(open_button)

        self._detail_page = QWidget()
        self._detail_title = QLabel("")
        self._detail_title.setObjectName("screenTitle")
        self._detail_meta = QLabel("")
        self._detail_meta.setObjectName("muted")
        self._detail_meta.setWordWrap(True)
        self._sessions = QTreeWidget()
        self._sessions.setHeaderLabels(["Session", "Heure", "Durée", "Taille"])
        self._sessions.setRootIsDecorated(False)
        back = QPushButton("Toutes les courses")
        back.clicked.connect(self.show_list)
        play = QPushButton("Lire")
        play.setObjectName("primary")
        play.clicked.connect(self._play)
        export_one = QPushButton("Exporter")
        export_one.clicked.connect(self._export_one)
        delete_one = QPushButton("Supprimer")
        delete_one.setObjectName("danger")
        delete_one.clicked.connect(self._delete_one)
        export_all = QPushButton("Exporter la course")
        export_all.clicked.connect(self._export_all)
        delete_all = QPushButton("Supprimer la course")
        delete_all.setObjectName("danger")
        delete_all.clicked.connect(self._delete_all)
        row = QHBoxLayout()
        row.addWidget(play)
        row.addWidget(export_one)
        row.addWidget(delete_one)
        row.addStretch(1)
        row.addWidget(export_all)
        row.addWidget(delete_all)
        detail_layout = QVBoxLayout(self._detail_page)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.addWidget(back)
        detail_layout.addWidget(self._detail_title)
        detail_layout.addWidget(self._detail_meta)
        detail_layout.addWidget(self._sessions, stretch=1)
        detail_layout.addLayout(row)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._list_page)
        layout.addWidget(self._detail_page)
        self._detail_page.hide()

    def show_courses(self, courses: list[CourseArchive]) -> None:
        self._courses = courses
        self._course = None
        self._list.clear()
        self._empty.setVisible(not courses)
        self._list.setVisible(bool(courses))
        for course in courses:
            stamp = course.date.strftime("%d/%m/%Y")
            text = (
                f"{course.course_name}\n{stamp}  ·  {course.session_count} session"
                f"{'s' if course.session_count > 1 else ''}  ·  "
                f"{format_duration_minutes(course.duration_total)} de vidéo"
            )
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, course.course_name)
            self._list.addItem(item)
        self._detail_page.hide()
        self._list_page.show()

    def open_course(self, course: CourseArchive) -> None:
        if all(item.course_name != course.course_name for item in self._courses):
            self._courses = [course, *self._courses]
        self._show_detail(course)

    def show_list(self) -> None:
        self._detail_page.hide()
        self._list_page.show()

    def current_course(self) -> CourseArchive | None:
        return self._course

    def selected_session(self) -> RecordedSession | None:
        item = self._sessions.currentItem()
        if item is None or self._course is None:
            return None
        session_id = item.data(0, Qt.ItemDataRole.UserRole)
        for session in self._course.sessions:
            if session.session_id == session_id:
                return session
        return None

    def _open_current(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        name = item.data(Qt.ItemDataRole.UserRole)
        course = next((entry for entry in self._courses if entry.course_name == name), None)
        if course is None:
            return
        self._show_detail(course)

    def _show_detail(self, course: CourseArchive) -> None:
        self._course = course
        self._detail_title.setText(course.course_name)
        self._detail_meta.setText(
            f"{course.date.strftime('%d/%m/%Y')}  ·  {course.session_count} session"
            f"{'s' if course.session_count > 1 else ''}  ·  "
            f"{format_duration_minutes(course.duration_total)}  ·  "
            f"{format_byte_size(course.size_total())}"
        )
        self._sessions.clear()
        for session in reversed(course.sessions):
            row = QTreeWidgetItem(
                [
                    f"Session {session.session_id:03d}",
                    session.start_time.strftime("%H:%M:%S"),
                    format_duration_minutes(session.duration_seconds),
                    format_byte_size(session.video_path.stat().st_size if session.video_path.is_file() else 0),
                ]
            )
            row.setData(0, Qt.ItemDataRole.UserRole, session.session_id)
            self._sessions.addTopLevelItem(row)
        if self._sessions.topLevelItemCount():
            self._sessions.setCurrentItem(self._sessions.topLevelItem(0))
        self._list_page.hide()
        self._detail_page.show()

    def _play(self) -> None:
        session = self.selected_session()
        if session is not None:
            self.play_requested.emit(session)

    def _export_one(self) -> None:
        session = self.selected_session()
        if session is not None:
            self.export_session_requested.emit(session)

    def _delete_one(self) -> None:
        session = self.selected_session()
        if session is not None:
            self.delete_session_requested.emit(session)

    def _export_all(self) -> None:
        if self._course is not None:
            self.export_course_requested.emit(self._course)

    def _delete_all(self) -> None:
        if self._course is not None:
            self.delete_course_requested.emit(self._course)
