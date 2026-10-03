"""Dernières secondes du direct, en JPEG, indexées par time.monotonic()."""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class BufferedFrame:
    monotonic_timestamp: float
    wall_clock_timestamp: datetime
    jpeg_data: bytes


@dataclass(frozen=True)
class BufferStats:
    frame_count: int
    duration_seconds: float
    memory_bytes: int


class RingBuffer:
    """Conserve les images dont l'âge ne dépasse pas max_seconds.

    L'âge est calculé avec les timestamps monotonic, pas avec un nombre
    d'images. snapshot_last_seconds renvoie une liste nouvelle qui référence
    les mêmes octets JPEG, sans les recopier. Le thread de capture peut
    ensuite ajouter ou oublier des images sans changer cette liste. Les
    octets restent en mémoire tant que le snapshot les référence.
    """

    def __init__(self, max_seconds: float) -> None:
        if max_seconds <= 0:
            raise ValueError("max_seconds must be positive")
        self.max_seconds = max_seconds
        self._frames: deque[BufferedFrame] = deque()
        self._memory_bytes = 0
        self._newest: float | None = None
        self._lock = threading.Lock()

    def append(self, frame: BufferedFrame) -> None:
        if not isinstance(frame.jpeg_data, bytes):
            raise TypeError("jpeg_data must be bytes")
        with self._lock:
            self._frames.append(frame)
            self._memory_bytes += len(frame.jpeg_data)
            if self._newest is None or frame.monotonic_timestamp > self._newest:
                self._newest = frame.monotonic_timestamp
            self._evict(self._newest)

    def snapshot_last_seconds(self, seconds: float) -> list[BufferedFrame]:
        if seconds <= 0:
            raise ValueError("seconds must be positive")
        with self._lock:
            if not self._frames:
                return []
            latest = self._frames[-1].monotonic_timestamp
            cutoff = latest - seconds
            return [frame for frame in self._frames if frame.monotonic_timestamp >= cutoff]

    def stats(self) -> BufferStats:
        with self._lock:
            return self._stats_unlocked()

    def clear(self) -> None:
        with self._lock:
            self._frames.clear()
            self._memory_bytes = 0
            self._newest = None

    def _evict(self, now: float) -> None:
        cutoff = now - self.max_seconds
        while self._frames and self._frames[0].monotonic_timestamp < cutoff:
            removed = self._frames.popleft()
            self._memory_bytes -= len(removed.jpeg_data)
        if not self._frames:
            self._memory_bytes = 0
            self._newest = None

    def _stats_unlocked(self) -> BufferStats:
        if not self._frames:
            return BufferStats(frame_count=0, duration_seconds=0.0, memory_bytes=0)
        duration = self._frames[-1].monotonic_timestamp - self._frames[0].monotonic_timestamp
        return BufferStats(
            frame_count=len(self._frames),
            duration_seconds=duration,
            memory_bytes=self._memory_bytes,
        )
