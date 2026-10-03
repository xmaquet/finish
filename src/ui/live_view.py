"""Zone d'image. Le ratio de la webcam est conservé."""

import cv2
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy


class LiveView(QLabel):
    def __init__(self) -> None:
        super().__init__()
        self._image: QImage | None = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(320, 180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background-color: #111111; color: #bbbbbb;")
        self.setText("Pas d'image")

    def set_frame_bgr(self, frame: np.ndarray) -> None:
        self._image = _bgr_frame_to_qimage(frame)
        self._update_pixmap()

    def clear_frame(self) -> None:
        self._image = None
        self.clear()
        self.setText("Pas d'image")

    def resizeEvent(self, event) -> None:  # noqa: N802 - signature Qt
        super().resizeEvent(event)
        self._update_pixmap()

    def _update_pixmap(self) -> None:
        if self._image is None or self.width() <= 0 or self.height() <= 0:
            return
        pixmap = QPixmap.fromImage(self._image)
        scaled = pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        self.setPixmap(scaled)


def _bgr_frame_to_qimage(frame: np.ndarray) -> QImage:
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    height, width, channels = rgb.shape
    return QImage(
        rgb.tobytes(),
        width,
        height,
        channels * width,
        QImage.Format.Format_RGB888,
    )
