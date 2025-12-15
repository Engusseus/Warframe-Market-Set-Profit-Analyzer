"""Analysis API routes."""
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request

from ...core.logging import get_logger
from ...models.schemas import (
    AnalysisConfig,
    AnalysisResponse,
    AnalysisStartedResponse,
    AnalysisStatusResponse,
    ScoredData,
    WeightsConfig,
)
from ...services.analysis_service import AnalysisService

router = APIRouter()

# Shared analysis service instance
_analysis_service: Optional[AnalysisService] = None


def get_analysis_service() -> AnalysisService:
    """Get or create analysis service instance."""
    global _analysis_service
    if _analysis_service is None:
        _analysis_service = AnalysisService()
    return _analysis_service


@router.get("", response_model=AnalysisResponse)
async def get_analysis(
    request: Request,
    force_refresh: bool = Query(False, description="Force fresh data fetch"),
    profit_weight: float = Query(1.0, ge=0.0, le=10.0, description="Profit weight"),
    volume_weight: float = Query(1.2, ge=0.0, le=10.0, description="Volume weight")
) -> AnalysisResponse:
    """Get analysis results.

    If no recent analysis exists or force_refresh is True, runs a new analysis.
    Otherwise returns the latest cached analysis.
    """
    logger = get_logger()
    logger.info(f"Analysis request received from {request.client.host if request.client else 'unknown'}")
    logger.info(f"Request params: force_refresh={force_refresh}, profit_weight={profit_weight}, volume_weight={volume_weight}")

    service = get_analysis_service()

    try:
        # Run full analysis
        result = await service.run_full_analysis(
            profit_weight=profit_weight,
            volume_weight=volume_weight,
            force_refresh=force_refresh
        )
        logger.info(f"Analysis completed successfully, returning {result.total_sets} sets")
        return result
    except Exception as e:
        logger.error(f"Analysis request failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=AnalysisStartedResponse)
async def trigger_analysis(
    background_tasks: BackgroundTasks,
    config: AnalysisConfig = None
) -> AnalysisStartedResponse:
    """Trigger a new analysis run in the background.

    Returns immediately with status, analysis runs asynchronously.
    """
    if config is None:
        config = AnalysisConfig()

    service = get_analysis_service()

    # Check if already running
    status = service.get_status()
    if status["status"] == "running":
        raise HTTPException(
            status_code=409,
            detail="Analysis already in progress"
        )

    # Start background analysis
    async def run_analysis():
        try:
            await service.run_full_analysis(
                profit_weight=config.profit_weight,
                volume_weight=config.volume_weight,
                force_refresh=config.force_refresh
            )
        except Exception:
            pass  # Status is updated in service

    background_tasks.add_task(run_analysis)

    return AnalysisStartedResponse(
        message="Analysis started",
        status="started",
        estimated_time_seconds=60
    )


@router.get("/status", response_model=AnalysisStatusResponse)
async def get_analysis_status() -> AnalysisStatusResponse:
    """Get current analysis status."""
    service = get_analysis_service()
    status = service.get_status()

    return AnalysisStatusResponse(
        status=status["status"],
        progress=status["progress"],
        message=status["message"],
        run_id=status["run_id"]
    )


@router.post("/rescore")
async def rescore_analysis(
    profit_weight: float = Query(1.0, ge=0.0, le=10.0),
    volume_weight: float = Query(1.2, ge=0.0, le=10.0)
):
    """Rescore existing analysis data with new weights.

    Does not fetch new data, just recalculates scores.
    """
    service = get_analysis_service()

    result = await service.recalculate_scores(profit_weight, volume_weight)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="No analysis data available. Run an analysis first."
        )

    # Convert to response format
    scored_models = [ScoredData(**item) for item in result]

    return {
        "sets": scored_models,
        "total_sets": len(scored_models),
        "weights": WeightsConfig(
            profit_weight=profit_weight,
            volume_weight=volume_weight
        )
    }
