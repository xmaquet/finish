"""Liste des sessions enregistrées, groupées par course."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from sessions.catalog import RecordedSession, format_duration_minutes


class ArchivePanel(QWidget):
    open_requested = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        title = QLabel("Sessions enregistrées")
        title.setStyleSheet("font-weight: 700; font-size: 16px;")
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Course", "Date", "Heure", "Session", "Durée"])
        self._tree.setColumnWidth(0, 220)
        self._tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self._tree.itemDoubleClicked.connect(self._emit_current)
        self._empty = QLabel("Aucune session enregistrée.")
        self._empty.hide()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(title)
        layout.addWidget(self._tree, stretch=1)
        layout.addWidget(self._empty)

    def show_groups(self, groups: list[tuple[str, list[RecordedSession]]]) -> None:
        self._tree.clear()
        self._empty.setVisible(not groups)
        self._tree.setVisible(bool(groups))
        for course_name, sessions in groups:
            parent = QTreeWidgetItem([course_name, "", "", "", ""])
            parent.setFlags(parent.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            for session in sessions:
                stamp = session.start_time
                child = QTreeWidgetItem(
                    [
                        "",
                        stamp.strftime("%d/%m/%Y"),
                        stamp.strftime("%H:%M:%S"),
                        f"Session {session.session_id:03d}",
                        format_duration_minutes(session.duration_seconds),
                    ]
                )
                child.setData(0, Qt.ItemDataRole.UserRole, session)
                parent.addChild(child)
            self._tree.addTopLevelItem(parent)
            parent.setExpanded(True)

    def selected_session(self) -> RecordedSession | None:
        item = self._tree.currentItem()
        if item is None:
            return None
        session = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(session, RecordedSession):
            return session
        return None

    def _emit_current(self, _item: QTreeWidgetItem, _column: int) -> None:
        session = self.selected_session()
        if session is not None:
            self.open_requested.emit(session)
