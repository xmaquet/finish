"""Liste des sessions enregistrées. Pas de base de données.

Le JSON est la source des informations affichées. Le nom de fichier sert
seulement à associer le MP4 et le JSON du même radical.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import cv2

from sessions.archive import match_session_filename
from sessions.metadata import SessionMetadata, read_metadata

logger = logging.getLogger("finish.archive")


@dataclass(frozen=True)
class RecordedSession:
    course_name: str
    course_slug: str
    session_id: int
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    video_path: Path
    metadata_path: Path
    width: int
    height: int
    measured_fps: float
    file_fps: float
    frames_written: int
    recording_dropped_frames: int
    codec: str
    camera_index: int
    backend: str
    pixel_format: str


def format_duration_minutes(seconds: float) -> str:
    """Durée courte pour la liste : 02:33, ou 01:02:03 à partir d'une heure."""
    whole = max(0, int(seconds))
    minutes, secs = divmod(whole, 60)
    if minutes >= 60:
        hours, minutes = divmod(minutes, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def session_summary(session: RecordedSession) -> str:
    stamp = session.start_time
    return (
        f"{session.course_name} | {stamp.strftime('%d/%m/%Y')} | "
        f"{stamp.strftime('%H:%M:%S')} | Session {session.session_id:03d} | "
        f"{format_duration_minutes(session.duration_seconds)}"
    )


def group_sessions(sessions: list[RecordedSession]) -> list[tuple[str, list[RecordedSession]]]:
    """Courses les plus récentes d'abord, et dans chaque course la session la plus récente d'abord."""
    ordered = sorted(sessions, key=lambda item: item.start_time, reverse=True)
    groups: list[tuple[str, list[RecordedSession]]] = []
    index_by_name: dict[str, int] = {}
    for session in ordered:
        key = session.course_name
        if key not in index_by_name:
            index_by_name[key] = len(groups)
            groups.append((key, []))
        groups[index_by_name[key]][1].append(session)
    return groups


def scan_recordings(directory: Path) -> list[RecordedSession]:
    if not directory.is_dir():
        return []
    sessions: list[RecordedSession] = []
    seen_stems: set[str] = set()
    json_paths = sorted(path for path in directory.iterdir() if path.is_file() and path.suffix.lower() == ".json")
    for json_path in json_paths:
        match = match_session_filename(json_path.name)
        if match is None:
            continue
        stem = json_path.stem
        seen_stems.add(stem)
        video_path = json_path.with_suffix(".mp4")
        if not video_path.is_file():
            logger.warning("Archive INCOMPLETE reason=missing-mp4 file=%s", json_path.name)
            continue
        session = _session_from_pair(json_path, video_path)
        if session is not None:
            sessions.append(session)
    for path in directory.iterdir():
        if not path.is_file() or path.suffix.lower() != ".mp4":
            continue
        if match_session_filename(path.name) is None or path.stem in seen_stems:
            continue
        logger.warning("Archive INCOMPLETE reason=missing-json file=%s", path.name)
    return sessions


def _session_from_pair(json_path: Path, video_path: Path) -> RecordedSession | None:
    try:
        metadata = read_metadata(json_path)
    except (OSError, ValueError, TypeError):
        logger.warning("Archive INVALID reason=bad-json file=%s", json_path.name)
        return None
    if metadata.video_file != video_path.name:
        logger.warning(
            "Archive INVALID reason=video-name-mismatch file=%s video_file=%s",
            json_path.name,
            metadata.video_file,
        )
        return None
    if not _video_opens(video_path):
        logger.warning("Archive INVALID reason=unreadable-video file=%s", video_path.name)
        return None
    try:
        start = datetime.fromisoformat(metadata.start_time)
        end = datetime.fromisoformat(metadata.end_time)
    except ValueError:
        logger.warning("Archive INVALID reason=bad-json file=%s", json_path.name)
        return None
    return _recorded(metadata, video_path, json_path, start, end)


def _video_opens(path: Path) -> bool:
    capture = cv2.VideoCapture(str(path))
    try:
        return bool(capture.isOpened())
    finally:
        capture.release()


def _recorded(
    metadata: SessionMetadata,
    video_path: Path,
    json_path: Path,
    start: datetime,
    end: datetime,
) -> RecordedSession:
    return RecordedSession(
        course_name=metadata.course_name,
        course_slug=metadata.course_slug,
        session_id=metadata.session_id,
        start_time=start,
        end_time=end,
        duration_seconds=float(metadata.duration_seconds),
        video_path=video_path,
        metadata_path=json_path,
        width=metadata.width,
        height=metadata.height,
        measured_fps=float(metadata.measured_fps),
        file_fps=float(metadata.file_fps),
        frames_written=metadata.frames_written,
        recording_dropped_frames=metadata.recording_dropped_frames,
        codec=metadata.codec,
        camera_index=metadata.camera_index,
        backend=metadata.backend,
        pixel_format=metadata.pixel_format,
    )
