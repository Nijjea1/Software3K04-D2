"""Module 1.1.5  Clock.

Responsibility : provide monotonic time to the rest of the system.
Secret         : the time source and its resolution.

Anticipated change: the platform clock is replaced, or resolution changes
from milliseconds to microseconds. Nothing above this module reads a raw
tick, so that change stops here.
"""
from abc import ABC, abstractmethod
import time


class Clock(ABC):
    """Exported interface. All times are whole seconds since an arbitrary epoch."""

    @abstractmethod
    def now_s(self) -> float:
        """Return monotonically non-decreasing seconds. Never goes backwards."""


class SystemClock(Clock):
    """Real implementation. i_tick is hidden inside here."""

    def now_s(self) -> float:
        return time.monotonic()


# Both classes sit behind the same Clock interface, so nothing above can tell
# which one it was given. That is the Week 6 slide 14 rule.
class SimulatedClock(Clock):
    """Simulated implementation used for the demonstration and the tests.

    Time only advances when advance() is called, so a 120 second session
    timeout can be demonstrated in front of the TAs without waiting.
    """

    def __init__(self, start_s: float = 0.0):
        self._t = float(start_s)

    def now_s(self) -> float:
        return self._t

    # Not part of the Clock interface. Only the demo and the tests call it, so
    # no behaviour module can move time on purpose.
    def advance(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("time cannot move backwards")
        self._t += seconds
