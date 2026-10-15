from core.rate_limit import SlidingWindowLimiter


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_allows_up_to_max_then_blocks():
    limiter = SlidingWindowLimiter(max_events=3, window_seconds=60, clock=Clock())
    assert [limiter.allow("a") for _ in range(4)] == [True, True, True, False]


def test_window_slides():
    clock = Clock()
    limiter = SlidingWindowLimiter(max_events=2, window_seconds=60, clock=clock)
    limiter.allow("a")
    clock.now = 30
    limiter.allow("a")
    assert not limiter.allow("a")
    clock.now = 61
    assert limiter.allow("a")


def test_keys_are_independent():
    limiter = SlidingWindowLimiter(max_events=1, window_seconds=60, clock=Clock())
    assert limiter.allow("telegram:1")
    assert limiter.allow("telegram:2")
    assert not limiter.allow("telegram:1")
