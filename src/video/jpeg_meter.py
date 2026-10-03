"""Cumul du coût JPEG. Une seule lecture synthétique, pas une ligne par image."""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True)
class JpegEncodeStats:
    count: int
    failures: int
    average_ms: float
    min_ms: float
    max_ms: float
    average_bytes: int
    min_bytes: int
    max_bytes: int


class JpegEncodeMeter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._count = 0
        self._failures = 0
        self._total_ms = 0.0
        self._total_bytes = 0
        self._min_ms: float | None = None
        self._max_ms: float | None = None
        self._min_bytes: int | None = None
        self._max_bytes: int | None = None

    def add_success(self, size_bytes: int, elapsed_ms: float) -> None:
        with self._lock:
            self._count += 1
            self._total_ms += elapsed_ms
            self._total_bytes += size_bytes
            self._min_ms = elapsed_ms if self._min_ms is None else min(self._min_ms, elapsed_ms)
            self._max_ms = elapsed_ms if self._max_ms is None else max(self._max_ms, elapsed_ms)
            self._min_bytes = size_bytes if self._min_bytes is None else min(self._min_bytes, size_bytes)
            self._max_bytes = size_bytes if self._max_bytes is None else max(self._max_bytes, size_bytes)

    def add_failure(self) -> None:
        with self._lock:
            self._failures += 1

    def snapshot(self) -> JpegEncodeStats:
        with self._lock:
            average_ms = self._total_ms / self._count if self._count else 0.0
            average_bytes = int(self._total_bytes / self._count) if self._count else 0
            return JpegEncodeStats(
                count=self._count,
                failures=self._failures,
                average_ms=average_ms,
                min_ms=0.0 if self._min_ms is None else self._min_ms,
                max_ms=0.0 if self._max_ms is None else self._max_ms,
                average_bytes=average_bytes,
                min_bytes=0 if self._min_bytes is None else self._min_bytes,
                max_bytes=0 if self._max_bytes is None else self._max_bytes,
            )
