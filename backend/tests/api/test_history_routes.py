"""API tests for history endpoints."""
import pytest
from httpx import AsyncClient


class TestGetHistory:
    """Tests for GET /api/history endpoint."""

    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_returns_history_structure(self, async_client: AsyncClient):
        """Test that history endpoint returns expected structure."""
        response = await async_client.get("/api/history")

        assert response.status_code == 200
        data = response.json()

        assert "runs" in data
        assert "total_runs" in data
        assert "page" in data
        assert "page_size" in data

    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_returns_list_of_runs(self, async_client: AsyncClient):
        """Test that runs is a list."""
        response = await async_client.get("/api/history")
        data = response.json()

        assert isinstance(data["runs"], list)

    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_pagination_parameters(self, async_client: AsyncClient):
        """Test that pagination parameters are accepted."""
        response = await async_client.get(
            "/api/history",
            params={"page": 1, "page_size": 5}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 5

    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_invalid_page_handled(self, async_client: AsyncClient):
        """Test that invalid page number is handled."""
        response = await async_client.get(
            "/api/history",
            params={"page": 0}  # Invalid page
        )

        # Should either handle gracefully or return 400
        assert response.status_code in [200, 400, 422]


class TestGetRunDetail:
    """Tests for GET /api/history/{run_id} endpoint."""

    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_returns_404_for_invalid_run_id(self, async_client: AsyncClient):
        """Test that invalid run_id returns 404."""
        response = await async_client.get("/api/history/99999")

        assert response.status_code == 404

    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_returns_detail_structure(self, async_client: AsyncClient):
        """Test that run detail has expected structure when found."""
        # First check if there are any runs
        history_response = await async_client.get("/api/history")
        history_data = history_response.json()

        if history_data["runs"]:
            run_id = history_data["runs"][0]["run_id"]
            response = await async_client.get(f"/api/history/{run_id}")

            assert response.status_code == 200
            data = response.json()
            assert "run_id" in data
            assert "date_string" in data


class TestGetHistoricalAnalysis:
    """Tests for GET /api/history/{run_id}/analysis endpoint."""

    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_returns_404_for_invalid_run_id(self, async_client: AsyncClient):
        """Test that invalid run_id returns 404."""
        response = await async_client.get("/api/history/99999/analysis")

        assert response.status_code == 404
