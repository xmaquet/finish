"""Prochain numéro de session, sans jamais réutiliser un fichier existant.

Le slug seul n'identifie pas un événement : la date et l'heure sont dans le
nom. On regarde malgré tout tous les fichiers de ce slug pour choisir un
numéro encore libre, y compris après un redémarrage de l'application.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sessions.names import recording_file_stem

_ARCHIVED_SESSION = re.compile(
    r"^(?P<stamp>\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})_(?P<slug>.+)_session-(?P<session>\d+)\.(?:mp4|json)$"
)


@dataclass(frozen=True)
class ReservedSession:
    session_id: int
    video_path: Path
    metadata_path: Path

    @property
    def session_id_label(self) -> str:
        return f"{self.session_id:03d}"


def match_session_filename(name: str) -> re.Match[str] | None:
    return _ARCHIVED_SESSION.match(name)


def session_ids_for_slug(directory: Path, course_slug: str) -> set[int]:
    if not directory.is_dir():
        return set()
    found: set[int] = set()
    for path in directory.iterdir():
        if not path.is_file():
            continue
        match = match_session_filename(path.name)
        if match is None or match.group("slug") != course_slug:
            continue
        found.add(int(match.group("session")))
    return found


def next_session_id(directory: Path, course_slug: str, *, minimum_id: int = 1) -> int:
    if minimum_id < 1:
        raise ValueError("minimum_id must be >= 1")
    used = session_ids_for_slug(directory, course_slug)
    return max([minimum_id - 1, *used]) + 1


def reserve_new_session(
    directory: Path,
    course_name: str,
    course_slug: str,
    start: datetime,
    *,
    minimum_id: int = 1,
) -> ReservedSession:
    """Choisit un couple mp4/json qui n'existe pas encore. Ne crée pas les fichiers."""
    directory.mkdir(parents=True, exist_ok=True)
    session_id = next_session_id(directory, course_slug, minimum_id=minimum_id)
    while True:
        stem = recording_file_stem(start, course_name, session_id)
        video_path = directory / f"{stem}.mp4"
        metadata_path = directory / f"{stem}.json"
        if not video_path.exists() and not metadata_path.exists():
            return ReservedSession(
                session_id=session_id,
                video_path=video_path,
                metadata_path=metadata_path,
            )
        session_id += 1
