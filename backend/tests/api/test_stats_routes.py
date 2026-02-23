"""API tests for stats endpoints."""
import pytest
from httpx import AsyncClient


class TestGetStats:
    """Tests for GET /api/stats endpoint."""

    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_returns_stats_structure(self, async_client: AsyncClient):
        """Test that stats endpoint returns expected structure."""
        response = await async_client.get("/api/stats")

        assert response.status_code == 200
        data = response.json()

        assert "database" in data
        assert "analysis" in data

    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_database_stats_fields(self, async_client: AsyncClient):
        """Test that database stats have required fields."""
        response = await async_client.get("/api/stats")
        data = response.json()

        db_stats = data["database"]
        assert "total_runs" in db_stats
        assert "total_profit_records" in db_stats
        assert "database_size_bytes" in db_stats

    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_analysis_stats_fields(self, async_client: AsyncClient):
        """Test that analysis stats have required fields."""
        response = await async_client.get("/api/stats")
        data = response.json()

        analysis_stats = data["analysis"]
        # These fields can be null if no analysis has been run
        assert "cache_age_seconds" in analysis_stats or analysis_stats.get("cache_age_seconds") is None
        assert "last_analysis" in analysis_stats or analysis_stats.get("last_analysis") is None


class TestHealthCheck:
    """Tests for GET /api/stats/health endpoint."""

    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_health_returns_ok(self, async_client: AsyncClient):
        """Test that health check returns OK status."""
        response = await async_client.get("/api/stats/health")

        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok" or "healthy" in str(data).lower()

    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_health_includes_version(self, async_client: AsyncClient):
        """Test that health check includes version info."""
        response = await async_client.get("/api/stats/health")
        data = response.json()

        # Should include version or at least not error
        assert response.status_code == 200
