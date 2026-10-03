"""Enregistrement MP4 hors du thread caméra.

La capture dépose l'image BGR déjà horodatée dans une file bornée.
Si la file est pleine, l'image nouvelle est abandonnée. La capture n'attend jamais.
Le worker écrit ces images telles quelles : il ne décode pas le JPEG du buffer.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from config import RECORDING_CODEC, RECORDING_QUEUE_MAX_FRAMES, REQUESTED_FPS
from sessions.archive import ReservedSession
from sessions.metadata import SessionMetadata, write_metadata

logger = logging.getLogger("finish.recorder")

_OVERFLOW_LOG_INTERVAL_SECONDS = 1.0


def file_frame_rate(measured_fps: float, fps_ready: bool, requested_fps: float = REQUESTED_FPS) -> float:
    """Cadence du conteneur, fixée à l'ouverture du fichier.

    Chaque image capturée est écrite une fois, sans rééchantillonnage.
    La durée lue vaut frames_écrites / file_fps. Si la mesure est déjà proche
    de la cadence demandée, on garde la cadence demandée : une mesure sur une
    seconde varie trop pour servir de diviseur. Si la caméra est vraiment
    ailleurs, on prend la mesure, arrondie au centième.
    """
    if not fps_ready or measured_fps < 5.0:
        return float(requested_fps)
    if abs(measured_fps - requested_fps) <= 2.0:
        return float(requested_fps)
    return round(float(measured_fps), 2)


class RecorderError(Exception):
    """Le fichier n'a pas pu être ouvert. Rien n'a été publié vers la capture."""


class RecordingQueue:
    """File bornée. offer() ne bloque pas."""

    def __init__(self, max_frames: int = RECORDING_QUEUE_MAX_FRAMES) -> None:
        if max_frames < 1:
            raise ValueError("max_frames must be >= 1")
        self._items: queue.Queue[np.ndarray] = queue.Queue(maxsize=max_frames)
        self._lock = threading.Lock()
        self._accepting = True
        self._dropped = 0
        self._last_overflow_log = 0.0

    def close(self) -> None:
        with self._lock:
            self._accepting = False

    def offer(self, frame: np.ndarray) -> bool:
        should_log = False
        dropped = 0
        with self._lock:
            if not self._accepting:
                return False
            try:
                self._items.put_nowait(frame)
                return True
            except queue.Full:
                self._dropped += 1
                dropped = self._dropped
                now = time.monotonic()
                if now - self._last_overflow_log >= _OVERFLOW_LOG_INTERVAL_SECONDS:
                    self._last_overflow_log = now
                    should_log = True
        if should_log:
            logger.warning("Recording queue overflow — dropped frame total=%s", dropped)
        return False

    def get(self, timeout: float) -> np.ndarray:
        return self._items.get(timeout=timeout)

    def empty(self) -> bool:
        return self._items.empty()

    @property
    def dropped_frames(self) -> int:
        with self._lock:
            return self._dropped

    @property
    def accepting(self) -> bool:
        with self._lock:
            return self._accepting


class SessionRecorder:
    """Ouvre un MP4, consomme la file, puis écrit le JSON."""

    def __init__(
        self,
        reserved: ReservedSession,
        *,
        course_name: str,
        course_slug: str,
        width: int,
        height: int,
        file_fps: float,
        camera_index: int,
        backend: str,
        pixel_format: str,
        requested_fps: float,
        measured_fps: float,
        codec: str = RECORDING_CODEC,
        max_frames: int = RECORDING_QUEUE_MAX_FRAMES,
    ) -> None:
        if reserved.video_path.exists() or reserved.metadata_path.exists():
            raise RecorderError("Un fichier de ce nom existe déjà.")
        if width < 1 or height < 1:
            raise RecorderError("Résolution d'enregistrement invalide.")
        if file_fps <= 0:
            raise RecorderError("Cadence d'enregistrement invalide.")
        if len(codec) != 4:
            raise RecorderError("Le codec doit faire quatre caractères.")
        self._reserved = reserved
        self._course_name = course_name
        self._course_slug = course_slug
        self._width = width
        self._height = height
        self._file_fps = float(file_fps)
        self._camera_index = camera_index
        self._backend = backend
        self._pixel_format = pixel_format
        self._requested_fps = float(requested_fps)
        self._measured_fps = float(measured_fps)
        self._codec = codec
        self._queue = RecordingQueue(max_frames)
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._state = "idle"
        self._frames_written = 0
        self._started_wall: datetime | None = None
        self._ended_wall: datetime | None = None
        self._started_mono: float | None = None
        self._ended_mono: float | None = None
        self._metadata: SessionMetadata | None = None
        self._thread: threading.Thread | None = None
        self._writer: cv2.VideoWriter | None = None

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    @property
    def frames_written(self) -> int:
        with self._lock:
            return self._frames_written

    @property
    def dropped_frames(self) -> int:
        return self._queue.dropped_frames

    @property
    def metadata(self) -> SessionMetadata | None:
        return self._metadata

    @property
    def elapsed_seconds(self) -> float:
        if self._started_mono is None:
            return 0.0
        end = self._ended_mono if self._ended_mono is not None else time.monotonic()
        return max(0.0, end - self._started_mono)

    def note_measured_fps(self, measured_fps: float) -> None:
        if measured_fps > 0:
            self._measured_fps = float(measured_fps)

    def offer(self, frame: np.ndarray) -> bool:
        if frame.ndim != 3 or frame.shape[2] != 3:
            return False
        if frame.shape[1] != self._width or frame.shape[0] != self._height:
            return False
        return self._queue.offer(frame)

    def start(self) -> None:
        if self._state != "idle":
            raise RecorderError("L'enregistreur est déjà démarré.")
        self._reserved.video_path.parent.mkdir(parents=True, exist_ok=True)
        if self._reserved.video_path.exists() or self._reserved.metadata_path.exists():
            raise RecorderError("Un fichier de ce nom existe déjà.")
        fourcc = cv2.VideoWriter_fourcc(*self._codec)
        writer = cv2.VideoWriter(
            str(self._reserved.video_path),
            fourcc,
            self._file_fps,
            (self._width, self._height),
        )
        if not writer.isOpened():
            writer.release()
            self._reserved.video_path.unlink(missing_ok=True)
            with self._lock:
                self._state = "error"
            raise RecorderError("Impossible d'ouvrir le fichier vidéo.")
        self._writer = writer
        self._started_wall = datetime.now()
        self._started_mono = time.monotonic()
        with self._lock:
            self._state = "recording"
        self._thread = threading.Thread(target=self._run, name="video-writer", daemon=False)
        self._thread.start()
        logger.info("Recording started file=%s", self._reserved.video_path.name)
        logger.info("Recording codec=%s", self._codec)
        logger.info("Recording fps=%.2f", self._file_fps)
        logger.info("Session id=%s", self._reserved.session_id)
        logger.info("RECORDER STARTED session_id=%03d", self._reserved.session_id)

    def stop(self, timeout: float) -> SessionMetadata | None:
        logger.info("RECORDER STOPPING session_id=%03d", self._reserved.session_id)
        if self._ended_mono is None:
            self._ended_mono = time.monotonic()
            self._ended_wall = datetime.now()
        self._queue.close()
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)
            if thread.is_alive():
                logger.error("Recorder thread still alive after %.1fs", timeout)
        if self._metadata is None and self._started_wall is not None:
            self._write_metadata()
        return self._metadata

    def _run(self) -> None:
        try:
            while True:
                try:
                    frame = self._queue.get(timeout=0.05)
                except queue.Empty:
                    if self._stop.is_set():
                        break
                    continue
                self._write_frame(frame)
        except Exception:
            logger.exception("Recorder worker failed")
            with self._lock:
                self._state = "error"
        finally:
            writer = self._writer
            self._writer = None
            if writer is not None:
                writer.release()
            self._write_metadata()
            with self._lock:
                if self._state == "recording":
                    self._state = "stopped"
            logger.info(
                "Recording stopped frames=%s dropped=%s",
                self.frames_written,
                self.dropped_frames,
            )
            logger.info(
                "RECORDER CLOSED session_id=%03d frames=%s dropped=%s",
                self._reserved.session_id,
                self.frames_written,
                self.dropped_frames,
            )

    def _write_frame(self, frame: np.ndarray) -> None:
        writer = self._writer
        if writer is None:
            return
        writer.write(frame)
        with self._lock:
            self._frames_written += 1

    def _write_metadata(self) -> None:
        if self._started_wall is None or self._ended_wall is None:
            return
        metadata = SessionMetadata(
            course_name=self._course_name,
            course_slug=self._course_slug,
            session_id=self._reserved.session_id,
            start_time=self._started_wall.isoformat(timespec="milliseconds"),
            end_time=self._ended_wall.isoformat(timespec="milliseconds"),
            duration_seconds=round(self.elapsed_seconds, 3),
            video_file=self._reserved.video_path.name,
            camera_index=self._camera_index,
            backend=self._backend,
            pixel_format=self._pixel_format,
            width=self._width,
            height=self._height,
            requested_fps=self._requested_fps,
            measured_fps=round(self._measured_fps, 2),
            file_fps=self._file_fps,
            codec=self._codec,
            frames_written=self.frames_written,
            recording_dropped_frames=self.dropped_frames,
        )
        write_metadata(self._reserved.metadata_path, metadata)
        self._metadata = metadata
