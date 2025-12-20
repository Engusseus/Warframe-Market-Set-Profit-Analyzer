"""API tests for export endpoints."""
import pytest
from httpx import AsyncClient


class TestGetExport:
    """Tests for GET /api/export endpoint."""

    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_returns_export_data(self, async_client: AsyncClient):
        """Test that export endpoint returns data."""
        response = await async_client.get("/api/export")

        assert response.status_code == 200
        data = response.json()

        assert "metadata" in data
        assert "market_runs" in data

    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_metadata_has_required_fields(self, async_client: AsyncClient):
        """Test that export metadata has required fields."""
        response = await async_client.get("/api/export")
        data = response.json()

        metadata = data["metadata"]
        assert "export_timestamp" in metadata
        assert "export_date" in metadata
        assert "total_runs" in metadata


class TestGetExportFile:
    """Tests for GET /api/export/file endpoint."""

    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_returns_json_file(self, async_client: AsyncClient):
        """Test that export file endpoint returns JSON content."""
        response = await async_client.get("/api/export/file")

        assert response.status_code == 200
        # Check content-type or content-disposition
        content_type = response.headers.get("content-type", "")
        content_disposition = response.headers.get("content-disposition", "")

        # Should be either JSON or octet-stream for download
        assert "json" in content_type or "octet-stream" in content_type or "attachment" in content_disposition

    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_file_has_content(self, async_client: AsyncClient):
        """Test that export file has content."""
        response = await async_client.get("/api/export/file")

        assert len(response.content) > 0


class TestGetExportSummary:
    """Tests for GET /api/export/summary endpoint."""

    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_returns_summary(self, async_client: AsyncClient):
        """Test that summary endpoint returns data."""
        response = await async_client.get("/api/export/summary")

        assert response.status_code == 200
        data = response.json()

        # Should have some summary info
        assert data is not None
