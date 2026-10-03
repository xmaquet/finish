"""Cadence observée à partir d'horodatages monotonic."""

from collections import deque


class FpsMeter:
    """FPS = (images - 1) / durée, sur une fenêtre glissante.

    Les temps doivent provenir de time.monotonic(). Une fenêtre vide ou un
    intervalle nul donne 0. ready devient vrai quand la fenêtre couvre
    environ la durée demandée.
    """

    def __init__(self, window_seconds: float = 1.0) -> None:
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self.window_seconds = window_seconds
        self._times: deque[float] = deque()

    def tick(self, now: float) -> float:
        self._times.append(now)
        cutoff = now - self.window_seconds
        while self._times and self._times[0] < cutoff:
            self._times.popleft()
        return self.value

    def reset(self) -> None:
        self._times.clear()

    @property
    def value(self) -> float:
        if len(self._times) < 2:
            return 0.0
        span = self._times[-1] - self._times[0]
        if span <= 0:
            return 0.0
        return (len(self._times) - 1) / span

    @property
    def ready(self) -> bool:
        if len(self._times) < 2:
            return False
        span = self._times[-1] - self._times[0]
        return span >= self.window_seconds * 0.9
