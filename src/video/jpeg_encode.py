"""Encodage JPEG d'une image déjà horodatée."""

from __future__ import annotations

import time

import cv2
import numpy as np


def encode_jpeg(frame: np.ndarray, quality: int) -> tuple[bytes | None, float]:
    """Retourne les octets JPEG et la durée en millisecondes."""
    started = time.perf_counter()
    success, encoded = cv2.imencode(
        ".jpg",
        frame,
        [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)],
    )
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    if not success:
        return None, elapsed_ms
    return encoded.tobytes(), elapsed_ms


def decode_jpeg(jpeg_data: bytes) -> tuple[np.ndarray | None, float]:
    """Décode une seule image. Les octets JPEG ne sont pas modifiés."""
    started = time.perf_counter()
    encoded = np.frombuffer(jpeg_data, dtype=np.uint8)
    frame = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    if frame is None:
        return None, elapsed_ms
    return frame, elapsed_ms
