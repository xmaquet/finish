"""Préférences de l'opérateur. JSON, sans base de données.

Le nom de la course n'est pas mémorisé : chaque course se saisit le jour même.
Un fichier absent ou illisible ramène les valeurs validées, et Finish démarre.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

from config import (
    CAMERA_INDEX,
    JPEG_QUALITY,
    MAX_BUFFER_SECONDS,
    REQUESTED_FPS,
    REQUESTED_HEIGHT,
    REQUESTED_WIDTH,
)

logger = logging.getLogger("finish.preferences")

_RESOLUTIONS = {(1920, 1080), (1280, 720), (640, 480)}
_FPS = {30, 25, 15}
_BUFFERS = {30, 20, 10}
_JPEG = {60, 80, 95}


@dataclass(frozen=True)
class Preferences:
    camera_index: int = CAMERA_INDEX
    width: int = REQUESTED_WIDTH
    height: int = REQUESTED_HEIGHT
    fps: int = REQUESTED_FPS
    buffer_seconds: int = MAX_BUFFER_SECONDS
    jpeg_quality: int = JPEG_QUALITY
    recordings_dir: str = ""
    place: str = ""


def default_preferences() -> Preferences:
    return Preferences()


def load_preferences(path: Path) -> Preferences:
    defaults = default_preferences()
    if not path.is_file():
        return defaults
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("Preferences unreadable, using defaults path=%s", path)
        return defaults
    if not isinstance(raw, dict):
        logger.warning("Preferences invalid, using defaults path=%s", path)
        return defaults
    width = _choice(_int(raw.get("width"), defaults.width), {item[0] for item in _RESOLUTIONS}, defaults.width)
    height = _choice(_int(raw.get("height"), defaults.height), {item[1] for item in _RESOLUTIONS}, defaults.height)
    if (width, height) not in _RESOLUTIONS:
        logger.warning("Preferences resolution rejected path=%s", path)
        width, height = defaults.width, defaults.height
    return Preferences(
        camera_index=max(0, _int(raw.get("camera_index"), defaults.camera_index)),
        width=width,
        height=height,
        fps=_choice(_int(raw.get("fps"), defaults.fps), _FPS, defaults.fps),
        buffer_seconds=_choice(
            _int(raw.get("buffer_seconds"), defaults.buffer_seconds),
            _BUFFERS,
            defaults.buffer_seconds,
        ),
        jpeg_quality=_choice(
            _int(raw.get("jpeg_quality"), defaults.jpeg_quality),
            _JPEG,
            defaults.jpeg_quality,
        ),
        recordings_dir=_text(raw.get("recordings_dir")),
        place=_text(raw.get("place")),
    )


def save_preferences(path: Path, preferences: Preferences) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(preferences)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _int(value: object, fallback: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return fallback
    return value


def _text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value


def _choice(value: int, allowed: set[int], fallback: int) -> int:
    if value in allowed:
        return value
    return fallback
