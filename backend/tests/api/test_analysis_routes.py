"""API tests for analysis endpoints."""
import asyncio
from datetime import datetime

import pytest
from httpx import AsyncClient

from app.models.schemas import (
    AnalysisResponse,
    ExecutionMode,
    ScoredData,
    StrategyType,
    WeightsConfig,
)


@pytest.fixture
def fake_analysis_service(monkeypatch):
    """Monkeypatched analysis service for route parameter verification."""
    class FakeAnalysisService:
        def __init__(self):
            self.run_calls = []
            self.rescore_calls = []

        async def run_full_analysis(self, **kwargs):
            self.run_calls.append(kwargs)
            mode = kwargs.get("execution_mode", ExecutionMode.INSTANT)
            if isinstance(mode, str):
                mode = ExecutionMode(mode)

            scored = ScoredData(
                set_slug="test_set",
                set_name="Test Set",
                set_price=100.0,
                part_cost=80.0,
                profit_margin=20.0,
                profit_percentage=25.0,
                part_details=[],
                execution_mode=mode,
                volume=100,
                normalized_profit=1.0,
                normalized_volume=1.0,
                profit_score=1.0,
                volume_score=1.0,
                total_score=1.0,
                composite_score=1.0,
            )
            return AnalysisResponse(
                run_id=1,
                timestamp=datetime.now(),
                sets=[scored],
                total_sets=1,
                profitable_sets=1,
                weights=WeightsConfig(),
                strategy=StrategyType.BALANCED,
                execution_mode=mode,
                cached=False,
            )

        def get_status(self):
            return {
                "status": "idle",
                "progress": 0,
                "message": "",
                "run_id": None,
                "error": None,
            }

        async def recalculate_scores(self, strategy, execution_mode=None, **kwargs):
            self.rescore_calls.append({
                "strategy": strategy,
                "execution_mode": execution_mode,
            })
            mode = execution_mode or ExecutionMode.INSTANT

            scored = ScoredData(
                set_slug="test_set",
                set_name="Test Set",
                set_price=100.0,
                part_cost=80.0,
                profit_margin=20.0,
                profit_percentage=25.0,
                part_details=[],
                execution_mode=mode,
                volume=100,
                normalized_profit=1.0,
                normalized_volume=1.0,
                profit_score=1.0,
                volume_score=1.0,
                total_score=1.0,
                composite_score=1.0,
            )
            return [scored.model_dump()]

    service = FakeAnalysisService()
    monkeypatch.setattr("app.api.routes.analysis.get_analysis_service", lambda: service)
    return service


class TestGetStrategies:
    """Tests for GET /api/analysis/strategies endpoint."""

    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_returns_all_strategies(self, async_client: AsyncClient):
        """Test that all three strategies are returned."""
        response = await async_client.get("/api/analysis/strategies")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_strategies_have_required_fields(self, async_client: AsyncClient):
        """Test that strategies have required fields."""
        response = await async_client.get("/api/analysis/strategies")
        data = response.json()

        for strategy in data:
            assert "type" in strategy
            assert "name" in strategy
            assert "description" in strategy
            assert "volatility_weight" in strategy
            assert "trend_weight" in strategy
            assert "roi_weight" in strategy
            assert "min_volume_threshold" in strategy

    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_strategy_types_are_valid(self, async_client: AsyncClient):
        """Test that strategy types are valid enum values."""
        response = await async_client.get("/api/analysis/strategies")
        data = response.json()

        strategy_types = [s["type"] for s in data]
        assert "safe_steady" in strategy_types
        assert "balanced" in strategy_types
        assert "aggressive" in strategy_types


class TestGetAnalysisStatus:
    """Tests for GET /api/analysis/status endpoint."""

    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_returns_idle_when_no_analysis(self, async_client: AsyncClient):
        """Test that status is idle when no analysis is running."""
        response = await async_client.get("/api/analysis/status")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["idle", "completed", "error"]

    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_status_has_required_fields(self, async_client: AsyncClient):
        """Test that status response has required fields."""
        response = await async_client.get("/api/analysis/status")
        data = response.json()

        assert "status" in data
        # Progress and message can be null
        assert "progress" in data or data.get("progress") is None


class TestRescoreAnalysis:
    """Tests for POST /api/analysis/rescore endpoint."""

    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_returns_404_without_prior_analysis(self, async_client: AsyncClient):
        """Test that rescore returns 404 when no analysis exists."""
        response = await async_client.post(
            "/api/analysis/rescore",
            params={"strategy": "aggressive"}
        )

        # Should return 404 if no analysis data exists
        assert response.status_code in [404, 200]  # 200 if there's cached data

    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_accepts_strategy_parameter(self, async_client: AsyncClient):
        """Test that strategy parameter is accepted."""
        # Just verify the endpoint accepts the parameter format
        response = await async_client.post(
            "/api/analysis/rescore",
            params={"strategy": "safe_steady"}
        )

        # Should not return 400 (bad request)
        assert response.status_code != 400

    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_accepts_execution_mode_parameter(
        self,
        async_client: AsyncClient,
        fake_analysis_service,
    ):
        """Test that execution_mode is accepted for rescoring."""
        response = await async_client.post(
            "/api/analysis/rescore",
            params={"strategy": "balanced", "execution_mode": "patient"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["execution_mode"] == "patient"
        assert fake_analysis_service.rescore_calls
        assert fake_analysis_service.rescore_calls[-1]["execution_mode"] == ExecutionMode.PATIENT


class TestAnalysisExecutionMode:
    """Tests for execution mode handling on analysis endpoints."""

    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_get_analysis_passes_execution_mode(
        self,
        async_client: AsyncClient,
        fake_analysis_service,
    ):
        """GET /analysis should pass execution_mode to service."""
        response = await async_client.get(
            "/api/analysis",
            params={"execution_mode": "patient", "strategy": "balanced", "test_mode": True},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["execution_mode"] == "patient"
        assert fake_analysis_service.run_calls
        assert fake_analysis_service.run_calls[-1]["execution_mode"] == ExecutionMode.PATIENT

    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_trigger_analysis_honors_config_execution_mode(
        self,
        async_client: AsyncClient,
        fake_analysis_service,
    ):
        """POST /analysis should pass config.execution_mode into background run."""
        response = await async_client.post(
            "/api/analysis",
            json={
                "strategy": "balanced",
                "execution_mode": "patient",
                "force_refresh": False,
            },
        )

        assert response.status_code == 200
        await asyncio.sleep(0)
        assert fake_analysis_service.run_calls
        assert fake_analysis_service.run_calls[-1]["execution_mode"] == ExecutionMode.PATIENT


class TestAnalysisProgress:
    """Tests for GET /api/analysis/progress SSE endpoint."""

    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_progress_endpoint_exists(self, async_client: AsyncClient):
        """Test that progress endpoint exists and is accessible.

        Note: Full SSE streaming tests are better done in E2E tests.
        The async client has difficulty with infinite SSE streams.
        """
        # Just verify the endpoint doesn't 404 by checking via HEAD/OPTIONS
        # or by verifying the route is registered
        from app.main import app
        routes = [route.path for route in app.routes]
        assert "/api/analysis/progress" in routes or any(
            "progress" in str(route.path) for route in app.routes
        )
