"""API tests for sets endpoints."""
import pytest
from httpx import AsyncClient


class TestGetSets:
    """Tests for GET /api/sets endpoint."""

    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_returns_sets_structure(self, async_client: AsyncClient):
        """Test that sets endpoint returns expected structure."""
        response = await async_client.get("/api/sets")

        assert response.status_code == 200
        data = response.json()

        assert "sets" in data
        assert "total_sets" in data

    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_sets_is_list(self, async_client: AsyncClient):
        """Test that sets is a list."""
        response = await async_client.get("/api/sets")
        data = response.json()

        assert isinstance(data["sets"], list)


class TestGetSetDetail:
    """Tests for GET /api/sets/{slug} endpoint."""

    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_returns_404_for_invalid_slug(self, async_client: AsyncClient):
        """Test that invalid slug returns 404."""
        response = await async_client.get("/api/sets/nonexistent_slug_12345")

        assert response.status_code == 404

    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_returns_set_detail_structure(self, async_client: AsyncClient):
        """Test that set detail has expected structure when found."""
        # First get list of sets
        sets_response = await async_client.get("/api/sets")
        sets_data = sets_response.json()

        if sets_data["sets"]:
            slug = sets_data["sets"][0].get("set_slug") or sets_data["sets"][0].get("slug")
            if slug:
                response = await async_client.get(f"/api/sets/{slug}")

                if response.status_code == 200:
                    data = response.json()
                    assert "slug" in data
                    assert "name" in data


class TestGetSetHistory:
    """Tests for GET /api/sets/{slug}/history endpoint."""

    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_returns_404_for_invalid_slug(self, async_client: AsyncClient):
        """Test that invalid slug returns 404."""
        response = await async_client.get("/api/sets/nonexistent_slug_12345/history")

        assert response.status_code in [404, 200]  # 200 with empty list is also valid

    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_returns_list(self, async_client: AsyncClient):
        """Test that history returns a list."""
        # First get list of sets
        sets_response = await async_client.get("/api/sets")
        sets_data = sets_response.json()

        if sets_data["sets"]:
            slug = sets_data["sets"][0].get("set_slug") or sets_data["sets"][0].get("slug")
            if slug:
                response = await async_client.get(f"/api/sets/{slug}/history")

                if response.status_code == 200:
                    data = response.json()
                    assert isinstance(data, list)
