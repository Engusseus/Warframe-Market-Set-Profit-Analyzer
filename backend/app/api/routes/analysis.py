"""Analysis API routes."""
import asyncio
import json
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

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
    test_mode: bool = Query(False, description="Run in test mode (limited data)"),
    profit_weight: float = Query(1.0, ge=0.0, le=10.0, description="Profit weight"),
    volume_weight: float = Query(1.2, ge=0.0, le=10.0, description="Volume weight")
) -> AnalysisResponse:
    """Get analysis results.

    If no recent analysis exists or force_refresh is True, runs a new analysis.
    Otherwise returns the latest cached analysis.
    """
    logger = get_logger()
    logger.info(f"Analysis request received from {request.client.host if request.client else 'unknown'}")
    logger.info(f"Request params: force_refresh={force_refresh}, test_mode={test_mode}, profit_weight={profit_weight}, volume_weight={volume_weight}")

    service = get_analysis_service()

    try:
        # Run full analysis
        result = await service.run_full_analysis(
            profit_weight=profit_weight,
            volume_weight=volume_weight,
            force_refresh=force_refresh,
            test_mode=test_mode
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


@router.get("/progress")
async def stream_analysis_progress(request: Request):
    """Stream analysis progress via Server-Sent Events (SSE).

    Returns real-time progress updates as the analysis runs.
    Connection stays open until analysis completes or client disconnects.
    """
    service = get_analysis_service()

    async def event_generator():
        """Generate SSE events for analysis progress."""
        last_progress = -1
        last_message = ""

        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                break

            status = service.get_status()
            current_progress = status["progress"]
            current_message = status["message"]
            current_status = status["status"]

            # Only send updates when there's a change
            if current_progress != last_progress or current_message != last_message or current_status in ["completed", "error"]:
                data = json.dumps({
                    "status": current_status,
                    "progress": current_progress,
                    "message": current_message,
                    "run_id": status["run_id"],
                    "error": status.get("error")
                })
                yield f"data: {data}\n\n"

                last_progress = current_progress
                last_message = current_message

                if current_status in ["completed", "error"]:
                    break

            # Poll interval - check status every 100ms
            await asyncio.sleep(0.1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
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
