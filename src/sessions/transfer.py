"""Copie des sessions vers un dossier choisi. Pas de réencodage.

Les originaux ne sont jamais effacés ici. L'interface ne propose la
suppression locale qu'après un export complet et vérifié.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from disk_space import free_bytes
from sessions.library import CourseArchive, session_size
from sessions.metadata import read_metadata, write_metadata
from version import VERSION

Progress = Callable[[int, int, int, int], None]


@dataclass(frozen=True)
class ExportResult:
    status: str
    message: str
    bytes_copied: int = 0
    files_copied: int = 0

    @property
    def succeeded(self) -> bool:
        return self.status == "success"


def may_remove_sources(result: ExportResult) -> bool:
    """Vrai seulement quand chaque fichier copié a été relu à la bonne taille."""
    return result.succeeded


def export_folder_name(course_name: str) -> str:
    cleaned = "".join(character for character in course_name if character not in '<>:"/\\|?*')
    cleaned = cleaned.strip().rstrip(".")
    return cleaned or "course"


def export_session(
    video: Path,
    metadata: Path | None,
    destination: Path,
    *,
    include_json: bool,
    free: int | None = None,
    cancel: threading.Event | None = None,
    progress: Progress | None = None,
) -> ExportResult:
    """Copie une session telle quelle, sous ses noms d'origine."""
    if not destination.is_dir():
        return ExportResult("missing_destination", "Le dossier de destination n'existe pas.")
    items = [video]
    if include_json:
        if metadata is None or not metadata.is_file():
            return ExportResult("missing_source", "Le JSON de la session est introuvable.")
        items.append(metadata)
    targets = [destination / path.name for path in items]
    return _copy_pairs(
        list(zip(items, targets, strict=True)),
        destination,
        free=free,
        cancel=cancel,
        progress=progress,
        manifest=None,
    )


def export_course(
    course: CourseArchive,
    destination: Path,
    *,
    free: int | None = None,
    cancel: threading.Event | None = None,
    progress: Progress | None = None,
    export_time: str | None = None,
    finish_version: str | None = None,
) -> ExportResult:
    """Dossier de course, sessions renommées session-001, et un course.json.

    Le MP4 est copié octet pour octet. Le JSON copié reçoit le nouveau nom
    de vidéo, pour que la paire reste lisible. L'original n'est pas modifié.
    """
    if not destination.is_dir():
        return ExportResult("missing_destination", "Le dossier de destination n'existe pas.")
    folder = destination / export_folder_name(course.course_name)
    pairs: list[tuple[Path, Path]] = []
    manifest_sessions = []
    for session in course.sessions:
        stem = f"session-{session.session_id:03d}"
        video_target = folder / f"{stem}.mp4"
        json_target = folder / f"{stem}.json"
        pairs.append((session.video_path, video_target))
        pairs.append((session.metadata_path, json_target))
        manifest_sessions.append(
            {
                "session_id": session.session_id,
                "video_file": video_target.name,
                "metadata_file": json_target.name,
                "start_time": session.start_time.isoformat(timespec="seconds"),
                "duration_seconds": session.duration_seconds,
                "size_bytes": session_size(session),
            }
        )
    manifest = {
        "course_name": course.course_name,
        "course_slug": course.course_slug,
        "date": course.date.strftime("%Y-%m-%d"),
        "session_count": course.session_count,
        "duration_seconds": round(course.duration_total, 3),
        "size_bytes": course.size_total(),
        "export_time": export_time or datetime.now().isoformat(timespec="seconds"),
        "finish_version": finish_version or VERSION,
        "sessions": manifest_sessions,
    }
    return _copy_pairs(
        pairs,
        folder,
        free=free,
        cancel=cancel,
        progress=progress,
        manifest=(folder / "course.json", manifest),
        rewrite_json=True,
    )


def delete_local_files(paths: list[Path]) -> int:
    """Suppression définitive. À n'appeler qu'après un export réussi."""
    freed = 0
    for path in paths:
        if path.is_file():
            freed += path.stat().st_size
            path.unlink()
    return freed


def _copy_pairs(
    pairs: list[tuple[Path, Path]],
    space_probe: Path,
    *,
    free: int | None,
    cancel: threading.Event | None,
    progress: Progress | None,
    manifest: tuple[Path, dict] | None,
    rewrite_json: bool = False,
) -> ExportResult:
    existing = [target for _source, target in pairs if target.exists()]
    if manifest is not None and manifest[0].exists():
        existing.append(manifest[0])
    if existing:
        return ExportResult("conflict", "Un fichier porte déjà ce nom dans la destination.")
    for source, _target in pairs:
        if not source.is_file():
            return ExportResult("missing_source", "Un fichier de la session est introuvable.")
    needed = sum(source.stat().st_size for source, _target in pairs)
    if manifest is not None:
        needed += len(json.dumps(manifest[1], ensure_ascii=False, indent=2).encode("utf-8")) + 1
    available = free if free is not None else _free_at(space_probe)
    if available < needed:
        return ExportResult("insufficient_space", "Espace insuffisant sur la destination.")
    copied_bytes = 0
    copied_files = 0
    total_files = len(pairs) + (1 if manifest is not None else 0)
    checked: list[tuple[Path, Path, int]] = []
    try:
        for source, target in pairs:
            if cancel is not None and cancel.is_set():
                return ExportResult("cancelled", "Export annulé.", copied_bytes, copied_files)
            if rewrite_json and source.suffix.lower() == ".json":
                written = _write_renamed_json(source, target)
            else:
                written = _copy_file(source, target, cancel, progress, copied_files, total_files, copied_bytes, needed)
            if written < 0:
                return ExportResult("cancelled", "Export annulé.", copied_bytes, copied_files)
            expected = written if rewrite_json and source.suffix.lower() == ".json" else source.stat().st_size
            if not _same_size(source, target, expected, rewritten=rewrite_json and source.suffix.lower() == ".json"):
                return ExportResult("verify_failed", "La copie n'a pas la taille attendue.", copied_bytes, copied_files)
            checked.append((source, target, expected))
            copied_bytes += target.stat().st_size
            copied_files += 1
            if progress is not None:
                progress(copied_files, total_files, copied_bytes, needed)
        if manifest is not None:
            path, payload = manifest
            path.parent.mkdir(parents=True, exist_ok=True)
            text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
            path.write_text(text, encoding="utf-8", newline="\n")
            expected_manifest = len(text.encode("utf-8"))
            if not path.is_file() or path.stat().st_size != expected_manifest:
                return ExportResult("verify_failed", "La copie n'a pas la taille attendue.", copied_bytes, copied_files)
            copied_bytes += path.stat().st_size
            copied_files += 1
            if progress is not None:
                progress(copied_files, total_files, copied_bytes, needed)
        for source, target, expected in checked:
            rewritten = rewrite_json and source.suffix.lower() == ".json"
            if not _same_size(source, target, expected, rewritten=rewritten):
                return ExportResult("verify_failed", "La copie n'a pas la taille attendue.", copied_bytes, copied_files)
    except OSError as error:
        return ExportResult("io_error", str(error), copied_bytes, copied_files)
    return ExportResult("success", "Export terminé.", copied_bytes, copied_files)


def _same_size(source: Path, target: Path, expected: int, *, rewritten: bool) -> bool:
    """Présence et taille. Un MP4 doit avoir la taille de l'original."""
    if not source.is_file() or not target.is_file():
        return False
    if target.stat().st_size != expected:
        return False
    if not rewritten and source.stat().st_size != target.stat().st_size:
        return False
    return True


def _write_renamed_json(source: Path, target: Path) -> int:
    metadata = read_metadata(source)
    updated = replace(metadata, video_file=target.with_suffix(".mp4").name)
    target.parent.mkdir(parents=True, exist_ok=True)
    write_metadata(target, updated)
    return target.stat().st_size


def _copy_file(
    source: Path,
    target: Path,
    cancel: threading.Event | None,
    progress: Progress | None,
    files_done: int,
    files_total: int,
    bytes_done: int,
    bytes_total: int,
) -> int:
    target.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with source.open("rb") as incoming, target.open("wb") as outgoing:
        while True:
            if cancel is not None and cancel.is_set():
                outgoing.close()
                target.unlink(missing_ok=True)
                return -1
            block = incoming.read(1024 * 1024)
            if not block:
                break
            outgoing.write(block)
            written += len(block)
            if progress is not None:
                progress(files_done, files_total, bytes_done + written, bytes_total)
    return written


def _free_at(path: Path) -> int:
    probe = path if path.exists() else path.parent
    return free_bytes(probe)
