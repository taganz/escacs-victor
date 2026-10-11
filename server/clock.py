"""Chess clock with Fischer increment.

Time is read from a monotonic source that can be replaced in tests.
"""

import time
from typing import Callable, Optional

import chess


class ChessClock:
    def __init__(
        self,
        initial: float = 600.0,
        increment: float = 5.0,
        now: Callable[[], float] = time.monotonic,
    ):
        self.initial = initial
        self.increment = increment
        self._now = now
        self._remaining = {chess.WHITE: float(initial), chess.BLACK: float(initial)}
        self.running: Optional[chess.Color] = None
        self._started_at = 0.0

    def start(self, color: chess.Color) -> None:
        """Start the clock of `color`. Any running clock is stopped first."""
        self.stop()
        self.running = color
        self._started_at = self._now()

    def stop(self) -> None:
        """Stop the running clock, keeping the time it has used."""
        if self.running is not None:
            self._remaining[self.running] = self.remaining(self.running)
            self.running = None

    def remaining(self, color: chess.Color) -> float:
        """Seconds left for `color`, never below 0."""
        value = self._remaining[color]
        if self.running == color:
            value -= self._now() - self._started_at
        return max(0.0, value)

    def flagged(self) -> Optional[chess.Color]:
        """The color whose running clock has reached 0, if any."""
        if self.running is not None and self.remaining(self.running) <= 0:
            return self.running
        return None

    def press(self) -> None:
        """The side to move has moved: stop its clock, add the increment
        and start the opponent's clock."""
        mover = self.running
        if mover is None:
            raise RuntimeError("The clock is not running")
        self.stop()
        self._remaining[mover] += self.increment
        self.start(not mover)
