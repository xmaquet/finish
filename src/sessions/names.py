"""Nom de course affiché, et forme utilisable dans un nom de fichier.

Le texte saisi reste intact pour l'opérateur et les futures métadonnées.
Le slug ne sert qu'au fichier. Un champ vide devient « Course ».
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime

from config import DEFAULT_COURSE_NAME, MAX_COURSE_SLUG_LENGTH

SLUG_FALLBACK = "session"
_APOSTROPHES = "'’`´"


def course_display_name(raw: str | None) -> str:
    """Nom humain. Seuls les blancs en bordure sont retirés."""
    if raw is None:
        return DEFAULT_COURSE_NAME
    stripped = raw.strip()
    if not stripped:
        return DEFAULT_COURSE_NAME
    return stripped


def make_course_slug(raw: str | None) -> str:
    """Forme stable pour un nom de fichier Windows, en minuscules ASCII."""
    text = course_display_name(raw)
    for character in _APOSTROPHES:
        text = text.replace(character, "")
    decomposed = unicodedata.normalize("NFKD", text)
    without_marks = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    slug = re.sub(r"[^a-z0-9]+", "-", without_marks.lower())
    slug = slug.strip("-")
    if len(slug) > MAX_COURSE_SLUG_LENGTH:
        slug = slug[:MAX_COURSE_SLUG_LENGTH].rstrip("-")
    return slug or SLUG_FALLBACK


def format_session_id(session_id: int) -> str:
    if session_id < 1:
        raise ValueError("session_id must be >= 1")
    return f"{session_id:03d}"


def recording_file_stem(start: datetime, course_name: str | None, session_id: int) -> str:
    """Nom sans extension : date, heure, course, session."""
    slug = make_course_slug(course_name)
    stamp = start.strftime("%Y-%m-%d_%H-%M-%S")
    return f"{stamp}_{slug}_session-{format_session_id(session_id)}"


def recording_filenames(
    start: datetime, course_name: str | None, session_id: int
) -> tuple[str, str]:
    stem = recording_file_stem(start, course_name, session_id)
    return f"{stem}.mp4", f"{stem}.json"
