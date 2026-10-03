"""Contrôles affichés avant de démarrer une course. Pas d'accès caméra ici."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Readiness:
    headline: str
    detail: str
    allowed: bool


def course_readiness(
    course_name: str,
    recordings_dir: Path,
    free_bytes_available: int,
    warning_below: int,
    *,
    camera_available: bool = True,
) -> Readiness:
    """Synthèse et droit de démarrer.

    Un disque faible prévient, sans bloquer. Un nom vide, une caméra absente
    ou un dossier inaccessible bloque.
    """
    if not course_name.strip():
        return Readiness("À vérifier", "Indiquez le nom de la course.", False)
    if not camera_available:
        return Readiness("À vérifier", "Aucune caméra détectée.", False)
    if not recordings_dir.is_dir() or not os.access(recordings_dir, os.W_OK):
        return Readiness("À vérifier", "Le dossier d'enregistrement n'est pas accessible.", False)
    if free_bytes_available < warning_below:
        return Readiness("À vérifier", "Attention : espace disque faible.", True)
    return Readiness("Prêt", "La course peut démarrer.", True)
