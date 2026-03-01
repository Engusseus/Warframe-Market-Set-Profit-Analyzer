"""Rate limiter for API requests.

Extracted from main.py lines 326-371. Converted to async for FastAPI compatibility.
"""
import asyncio
import time
from collections import deque
from typing import Deque


class RateLimiter:
    """Rate limiter to ensure max requests per time window.

    Uses a strict queued window scheduler. Across any ``time_window`` span,
    at most ``max_requests`` calls are permitted, and concurrent callers are
    serialized by reserving future slots.
    """

    def __init__(self, max_requests: int = 3, time_window: float = 1.0):
        """Initialize the rate limiter.

        Args:
            max_requests: Maximum number of requests allowed in time window
            time_window: Time window in seconds

        Raises:
            ValueError: If max_requests or time_window is not positive
        """
        if max_requests <= 0:
            raise ValueError("max_requests must be positive")
        if time_window <= 0:
            raise ValueError("time_window must be positive")

        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: Deque[float] = deque()
        self._lock = asyncio.Lock()

    def _cleanup_old_requests(self, current_time: float) -> None:
        """Remove requests older than time_window."""
        while self.requests and current_time - self.requests[0] >= self.time_window:
            self.requests.popleft()

    def _reserve_slot(self) -> float:
        """Reserve the next queued request slot.

        Returns:
            Sleep time in seconds before the caller can proceed.
        """
        current_time = time.monotonic()
        self._cleanup_old_requests(current_time)

        if len(self.requests) < self.max_requests:
            scheduled_time = current_time
        else:
            # Enforce no more than `max_requests` within any `time_window`.
            # Compare against the request `max_requests` slots behind.
            scheduled_time = max(
                current_time,
                self.requests[-self.max_requests] + self.time_window,
            )

        self.requests.append(scheduled_time)
        return max(0.0, scheduled_time - current_time)

    async def wait_if_needed(self) -> None:
        """Wait if necessary to maintain rate limit.

        This method is fully async-safe and serializes slot reservation
        across concurrent callers.
        """
        async with self._lock:
            sleep_time = self._reserve_slot()

        if sleep_time > 0:
            await asyncio.sleep(sleep_time)

    def get_current_rate(self) -> int:
        """Get the current number of requests in the time window."""
        current_time = time.monotonic()
        self._cleanup_old_requests(current_time)
        return sum(1 for request_time in self.requests if request_time <= current_time)

    def wait_if_needed_sync(self) -> None:
        """Synchronous version for non-async contexts.

        Preserved for backwards compatibility with sync code.
        """
        sleep_time = self._reserve_slot()
        if sleep_time > 0:
            time.sleep(sleep_time)
