import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    """Limite de eventos por chave numa janela deslizante, em memoria.
    Suficiente para um unico processo (um worker do uvicorn)."""

    def __init__(self, max_events: int, window_seconds: float, clock=time.monotonic):
        self._max = max_events
        self._window = window_seconds
        self._clock = clock
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = self._clock()
        events = self._events[key]
        while events and now - events[0] >= self._window:
            events.popleft()
        if len(events) >= self._max:
            return False
        events.append(now)
        return True
