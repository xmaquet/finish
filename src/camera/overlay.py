"""Dessin de l'horodatage dans le coin supérieur gauche."""

import cv2
import numpy as np


def draw_timestamp(frame: np.ndarray, text: str) -> None:
    """Modifie l'image BGR sur place. L'appelant ne doit plus la modifier ensuite."""
    if frame.ndim != 3 or frame.shape[2] != 3:
        raise ValueError("expected a BGR image")

    height, width = frame.shape[:2]
    scale = max(0.7, min(1.6, width / 1200))
    thickness = 2 if scale >= 1.0 else 1
    font = cv2.FONT_HERSHEY_SIMPLEX
    (text_width, text_height), baseline = cv2.getTextSize(text, font, scale, thickness)

    margin = max(8, int(12 * scale))
    padding = max(4, int(8 * scale))
    origin_x = margin
    origin_y = margin + text_height

    left = max(0, origin_x - padding)
    top = max(0, origin_y - text_height - padding)
    right = min(width - 1, origin_x + text_width + padding)
    bottom = min(height - 1, origin_y + baseline + padding)

    cv2.rectangle(frame, (left, top), (right, bottom), (0, 0, 0), thickness=-1)
    cv2.putText(
        frame,
        text,
        (origin_x, origin_y),
        font,
        scale,
        (255, 255, 255),
        thickness,
        cv2.LINE_AA,
    )
