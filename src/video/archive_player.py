"""Lecture d'un MP4 déjà enregistré. Ni caméra, ni buffer, ni replay live.

L'horloge visible est celle incrustée à la capture. Ce lecteur ne la redessine pas.

Le recul d'une image utilise CAP_PROP_POS_FRAMES. Sur les MP4 mp4v produits ici,
demander l'index N puis lire renvoie cette image, et la position devient N+1.
Si un codec futur se cale sur une image-clé à la place, le journal signale
l'écart et l'image affichée est celle que le décodeur a réellement fournie.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger("finish.archive")


def frame_index_for_seconds(seconds: float, file_fps: float, frame_count: int) -> int:
    if frame_count <= 0 or file_fps <= 0:
        return 0
    index = int(seconds * file_fps)
    return max(0, min(frame_count - 1, index))


def seconds_for_frame(index: int, file_fps: float) -> float:
    if file_fps <= 0:
        return 0.0
    return max(0, index) / file_fps


def natural_playback_fps(
    frames_written: int,
    duration_seconds: float,
    measured_fps: float,
    file_fps: float,
) -> float:
    """Cadence qui fait avancer l'horloge incrustée en temps réel.

    Le conteneur est souvent plus rapide que la capture. Lire à file_fps
    accélère la session. La vitesse normale est le nombre d'images divisé
    par la durée réelle.
    """
    if frames_written > 0 and duration_seconds > 0:
        return frames_written / duration_seconds
    if measured_fps > 1:
        return measured_fps
    if file_fps > 0:
        return file_fps
    return 30.0


def frame_index_for_wall_clock(
    start: datetime,
    target: datetime,
    file_fps: float,
    frame_count: int,
) -> int:
    """Index d'une heure demandée, à partir de start_time et de file_fps.

    L'horloge incrustée peut différer de quelques dixièmes, parce que la durée
    du fichier est frames / file_fps et non l'horloge murale. Une image à
    30 fps représente environ 33 ms. Ce n'est pas un chronométrage.
    """
    return frame_index_for_seconds((target - start).total_seconds(), file_fps, frame_count)


_CLOCK_TEXT = re.compile(r"^(\d{1,2}):(\d{2}):(\d{2})(?:\.(\d{1,3}))?$")


def parse_clock_text(text: str) -> tuple[int, int, int, int] | None:
    """HH:MM:SS ou HH:MM:SS.mmm. Les millisecondes incomplètes sont complétées à droite."""
    match = _CLOCK_TEXT.fullmatch(text.strip())
    if match is None:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2))
    second = int(match.group(3))
    fraction = match.group(4)
    millis = int(fraction.ljust(3, "0")) if fraction else 0
    if hour > 23 or minute > 59 or second > 59:
        return None
    return hour, minute, second, millis


def locate_frame_for_clock_text(
    start: datetime,
    text: str,
    file_fps: float,
    frame_count: int,
) -> tuple[int, str] | None:
    """Index et position : inside, before ou after.

    L'heure est posée sur le jour de start_time. Avant le début, l'index est 0.
    Après la dernière image, l'index est la dernière. None si le texte est illisible.
    """
    parsed = parse_clock_text(text)
    if parsed is None or frame_count < 1:
        return None
    hour, minute, second, millis = parsed
    target = start.replace(
        hour=hour,
        minute=minute,
        second=second,
        microsecond=millis * 1000,
    )
    delta = (target - start).total_seconds()
    if delta < 0:
        return 0, "before"
    index = frame_index_for_seconds(delta, file_fps, frame_count)
    if file_fps > 0 and delta * file_fps >= frame_count:
        return frame_count - 1, "after"
    return index, "inside"


class ArchivePlayer:
    def __init__(self) -> None:
        self._capture: cv2.VideoCapture | None = None
        self._index = -1
        self._frame: np.ndarray | None = None
        self._count = 0
        self._fps = 0.0
        self._mismatch_logged = False

    @property
    def is_open(self) -> bool:
        return self._capture is not None

    @property
    def frame_index(self) -> int:
        return self._index

    @property
    def frame_count(self) -> int:
        return self._count

    @property
    def file_fps(self) -> float:
        return self._fps

    @property
    def frame(self) -> np.ndarray | None:
        return self._frame

    def open(self, path: Path, file_fps: float) -> bool:
        self.close()
        capture = cv2.VideoCapture(str(path))
        if not capture.isOpened():
            capture.release()
            return False
        count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if count < 1:
            capture.release()
            return False
        self._capture = capture
        self._count = count
        reported = float(capture.get(cv2.CAP_PROP_FPS))
        self._fps = file_fps if file_fps > 0 else reported
        self._index = -1
        self._frame = None
        self._mismatch_logged = False
        return self.seek(0)

    def close(self) -> None:
        capture = self._capture
        self._capture = None
        self._frame = None
        self._index = -1
        self._count = 0
        if capture is not None:
            capture.release()

    def step(self, delta: int) -> bool:
        if delta == 0 or self._capture is None:
            return False
        return self.seek(self._index + delta)

    def seek(self, index: int) -> bool:
        capture = self._capture
        if capture is None or self._count < 1:
            return False
        index = max(0, min(self._count - 1, index))
        if index == self._index and self._frame is not None:
            return True
        capture.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = capture.read()
        if not ok or frame is None:
            return False
        reported = int(capture.get(cv2.CAP_PROP_POS_FRAMES))
        shown = index
        if reported != index + 1:
            if not self._mismatch_logged:
                logger.warning("Archive seek mismatch requested=%s reported=%s", index, reported)
                self._mismatch_logged = True
            if reported > 0:
                shown = min(self._count - 1, reported - 1)
        self._index = shown
        self._frame = frame
        return True
