"""Rate limiter for API requests.

Extracted from main.py lines 326-371. Converted to async for FastAPI compatibility.
"""
import asyncio
import time
from collections import deque
from typing import Deque


class RateLimiter:
    """Rate limiter to ensure max requests per time window.

    Uses a token bucket algorithm with a deque for efficient operations.
    Converted to async for use with FastAPI and httpx.
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

    async def wait_if_needed(self) -> None:
        """Wait if necessary to maintain rate limit.

        This is an async method that will yield control while waiting,
        allowing other coroutines to run without blocking the lock.
        """
        while True:
            sleep_time = 0
            async with self._lock:
                current_time = time.monotonic()
                
                # Remove requests older than time_window
                self._cleanup_old_requests(current_time)
                
                # If we're at the limit, calculate sleep time
                if len(self.requests) >= self.max_requests:
                    oldest_request_time = self.requests[0]
                    sleep_time = self.time_window - (current_time - oldest_request_time)
                else:
                    # We have capacity, record request and return
                    self.requests.append(current_time)
                    return
            
            # Wait outside the lock if necessary
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

    def get_current_rate(self) -> int:
        """Get the current number of requests in the time window."""
        current_time = time.monotonic()
        self._cleanup_old_requests(current_time)
        return len(self.requests)

    def wait_if_needed_sync(self) -> None:
        """Synchronous version for non-async contexts.

        Preserved for backwards compatibility with sync code.
        """
        current_time = time.monotonic()

        # Remove requests older than time_window
        self._cleanup_old_requests(current_time)

        # If we're at the limit, wait until the oldest request expires
        if len(self.requests) >= self.max_requests:
            # Calculate when the oldest request will expire
            oldest_request_time = self.requests[0]
            sleep_time = self.time_window - (current_time - oldest_request_time)

            if sleep_time > 0:
                time.sleep(sleep_time)

                # Clean up after waiting
                current_time = time.monotonic()
                self._cleanup_old_requests(current_time)

        # Record this request
        self.requests.append(current_time)
