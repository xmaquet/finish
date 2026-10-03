"""Lecture d'un instantané JPEG. Ce lecteur ne connaît ni la caméra ni le buffer."""

from __future__ import annotations

from dataclasses import dataclass

from video.ring_buffer import BufferedFrame


@dataclass(frozen=True)
class ReplayView:
    index: int
    jpeg_data: bytes | None
    elapsed_seconds: float
    duration_seconds: float
    paused: bool
    finished: bool
    requested_seconds: float


class ReplayPlayer:
    """Joue un snapshot à la vitesse des timestamps monotonic.

    La liste interne référence les mêmes octets JPEG que le snapshot.
    Une seule image est désignée à la fois : le décodage est fait par l'interface.
    """

    def __init__(self, frames: list[BufferedFrame], requested_seconds: float) -> None:
        if requested_seconds <= 0:
            raise ValueError("requested_seconds must be positive")
        self._frames = tuple(frames)
        self.requested_seconds = requested_seconds
        self._index = 0
        self._paused = False
        self._started = False
        self._anchor_now = 0.0
        self._anchor_frame = 0.0

    @property
    def paused(self) -> bool:
        return self._paused

    @property
    def frame_count(self) -> int:
        return len(self._frames)

    @property
    def duration_seconds(self) -> float:
        if len(self._frames) < 2:
            return 0.0
        return self._frames[-1].monotonic_timestamp - self._frames[0].monotonic_timestamp

    def start(self, now: float) -> None:
        self._started = True
        self._paused = False
        self._index = 0
        self._anchor_now = now
        if self._frames:
            self._anchor_frame = self._frames[0].monotonic_timestamp

    def advance(self, now: float) -> ReplayView:
        if not self._frames:
            return self._view(finished=True)
        if not self._started:
            self.start(now)
        if self._paused:
            return self._view(finished=False)
        target = self._anchor_frame + (now - self._anchor_now)
        last = self._frames[-1].monotonic_timestamp
        if target > last:
            return self._view(finished=True)
        while (
            self._index + 1 < len(self._frames)
            and self._frames[self._index + 1].monotonic_timestamp <= target
        ):
            self._index += 1
        return self._view(finished=False)

    def pause(self) -> None:
        self._paused = True

    def resume(self, now: float) -> None:
        if not self._frames:
            return
        self._paused = False
        self._anchor_now = now
        self._anchor_frame = self._frames[self._index].monotonic_timestamp

    def step(self, delta: int) -> None:
        if not self._paused or not self._frames or delta == 0:
            return
        last_index = len(self._frames) - 1
        self._index = min(max(self._index + delta, 0), last_index)

    def mode_label(self) -> str:
        if self.duration_seconds + 0.4 >= self.requested_seconds:
            shown = (
                int(self.requested_seconds)
                if float(self.requested_seconds).is_integer()
                else self.requested_seconds
            )
            return f"REPLAY — {shown} s"
        return f"REPLAY — {self.duration_seconds:.1f} s"

    def progress_label(self, elapsed_seconds: float) -> str:
        return f"{elapsed_seconds:.1f} / {self.duration_seconds:.1f} s"

    def _view(self, finished: bool) -> ReplayView:
        if not self._frames:
            return ReplayView(0, None, 0.0, 0.0, self._paused, True, self.requested_seconds)
        frame = self._frames[self._index]
        elapsed = frame.monotonic_timestamp - self._frames[0].monotonic_timestamp
        return ReplayView(
            index=self._index,
            jpeg_data=None if finished else frame.jpeg_data,
            elapsed_seconds=elapsed,
            duration_seconds=self.duration_seconds,
            paused=self._paused,
            finished=finished,
            requested_seconds=self.requested_seconds,
        )
