"""Métadonnées d'une session, écrites après la fermeture du MP4."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class SessionMetadata:
    course_name: str
    course_slug: str
    session_id: int
    start_time: str
    end_time: str
    duration_seconds: float
    video_file: str
    camera_index: int
    backend: str
    pixel_format: str
    width: int
    height: int
    requested_fps: float
    measured_fps: float
    file_fps: float
    codec: str
    frames_written: int
    recording_dropped_frames: int


def write_metadata(path: Path, metadata: SessionMetadata) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(asdict(metadata), ensure_ascii=False, indent=2)
    path.write_text(payload + "\n", encoding="utf-8")


def read_metadata(path: Path) -> SessionMetadata:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return SessionMetadata(**raw)
