"""Unit tests for rate limiter."""
import asyncio
import time

import pytest

from app.core.rate_limiter import RateLimiter


class TestRateLimiterInit:
    """Tests for RateLimiter initialization."""

    @pytest.mark.unit
    def test_creates_with_valid_params(self):
        """Test that RateLimiter creates with valid parameters."""
        limiter = RateLimiter(max_requests=5, time_window=2.0)
        assert limiter.max_requests == 5
        assert limiter.time_window == 2.0

    @pytest.mark.unit
    def test_raises_on_zero_max_requests(self):
        """Test that zero max_requests raises ValueError."""
        with pytest.raises(ValueError, match="max_requests must be positive"):
            RateLimiter(max_requests=0, time_window=1.0)

    @pytest.mark.unit
    def test_raises_on_negative_max_requests(self):
        """Test that negative max_requests raises ValueError."""
        with pytest.raises(ValueError, match="max_requests must be positive"):
            RateLimiter(max_requests=-1, time_window=1.0)

    @pytest.mark.unit
    def test_raises_on_zero_time_window(self):
        """Test that zero time_window raises ValueError."""
        with pytest.raises(ValueError, match="time_window must be positive"):
            RateLimiter(max_requests=5, time_window=0)

    @pytest.mark.unit
    def test_raises_on_negative_time_window(self):
        """Test that negative time_window raises ValueError."""
        with pytest.raises(ValueError, match="time_window must be positive"):
            RateLimiter(max_requests=5, time_window=-1.0)


class TestRateLimiterSync:
    """Tests for synchronous rate limiter methods."""

    @pytest.mark.unit
    def test_get_current_rate_initially_zero(self):
        """Test that current rate is initially zero."""
        limiter = RateLimiter(max_requests=3, time_window=1.0)
        assert limiter.get_current_rate() == 0

    @pytest.mark.unit
    def test_sync_wait_increments_count(self):
        """Test that sync wait increments request count."""
        limiter = RateLimiter(max_requests=10, time_window=1.0)
        limiter.wait_if_needed_sync()
        assert limiter.get_current_rate() == 1
        limiter.wait_if_needed_sync()
        assert limiter.get_current_rate() == 2

    @pytest.mark.unit
    def test_old_requests_cleaned_up(self):
        """Test that old requests are cleaned up after time window."""
        limiter = RateLimiter(max_requests=3, time_window=0.05)

        # Make some requests
        limiter.wait_if_needed_sync()
        limiter.wait_if_needed_sync()
        assert limiter.get_current_rate() == 2

        # Wait for time window to pass
        time.sleep(0.1)

        # Old requests should be cleaned up
        assert limiter.get_current_rate() == 0


class TestRateLimiterAsync:
    """Tests for async rate limiter methods."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_async_wait_increments_count(self):
        """Test that async wait increments request count."""
        limiter = RateLimiter(max_requests=10, time_window=1.0)
        await limiter.wait_if_needed()
        assert limiter.get_current_rate() == 1
        await limiter.wait_if_needed()
        assert limiter.get_current_rate() == 2

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_async_wait_respects_limit(self):
        """Test that async wait respects rate limit."""
        limiter = RateLimiter(max_requests=3, time_window=0.1)

        start_time = time.time()

        # Make 4 requests (exceeds limit of 3)
        for _ in range(4):
            await limiter.wait_if_needed()

        elapsed = time.time() - start_time

        # Should have waited at least time_window seconds
        assert elapsed >= 0.1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_async_wait_allows_concurrent_within_limit(self):
        """Test that concurrent requests within limit are allowed."""
        limiter = RateLimiter(max_requests=5, time_window=1.0)

        start_time = time.time()

        # Make 5 requests (at the limit)
        for _ in range(5):
            await limiter.wait_if_needed()

        elapsed = time.time() - start_time

        # Should complete almost instantly (no waiting)
        assert elapsed < 0.1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_async_cleanup_after_window(self):
        """Test that async operations clean up after time window."""
        limiter = RateLimiter(max_requests=3, time_window=0.05)

        # Fill up the limit
        for _ in range(3):
            await limiter.wait_if_needed()

        assert limiter.get_current_rate() == 3

        # Wait for window to pass
        await asyncio.sleep(0.1)

        # Should be clean now
        assert limiter.get_current_rate() == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_concurrent_async_access(self):
        """Test that concurrent async access is properly serialized."""
        limiter = RateLimiter(max_requests=5, time_window=0.5)

        async def make_requests():
            for _ in range(3):
                await limiter.wait_if_needed()

        # Run multiple concurrent tasks
        await asyncio.gather(make_requests(), make_requests())

        # Should have 6 total requests, properly rate limited
        assert limiter.get_current_rate() <= 5  # Can't exceed limit in window
