"""Fond photographique de la fenêtre. L'image source n'est pas modifiée."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QWidget


class AppBackdrop(QWidget):
    """Image couvrante, avec un léger voile pour garder le texte lisible."""

    def __init__(self, image_path: Path) -> None:
        super().__init__()
        self.setObjectName("app")
        self._source = QPixmap(str(image_path)) if image_path.is_file() else QPixmap()
        self._scaled: QPixmap | None = None
        self._scaled_size = None

    def paintEvent(self, event) -> None:  # noqa: N802 - signature Qt
        del event
        painter = QPainter(self)
        if self._source.isNull():
            painter.fillRect(self.rect(), QColor("#f4f6f8"))
            return
        size = self.size()
        if self._scaled is None or self._scaled_size != size:
            self._scaled = self._cover(size)
            self._scaled_size = size
        painter.drawPixmap(0, 0, self._scaled)
        painter.fillRect(self.rect(), QColor(255, 255, 255, 56))

    def _cover(self, size) -> QPixmap:
        scaled = self._source.scaled(
            size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        canvas = QPixmap(size)
        canvas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(canvas)
        x = (size.width() - scaled.width()) // 2
        y = (size.height() - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)
        painter.end()
        return canvas
