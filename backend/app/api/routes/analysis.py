"""Analysis API routes."""
import asyncio
import json
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from ...core.logging import get_logger
from ...core.strategy_profiles import StrategyType
from ...models.schemas import (
    AnalysisConfig,
    AnalysisResponse,
    AnalysisStartedResponse,
    AnalysisStatusResponse,
    ExecutionMode,
    ScoredData,
    StrategyProfileResponse,
    StrategyType as SchemaStrategyType,
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


def _parse_execution_mode(execution_mode: str) -> ExecutionMode:
    """Parse execution mode with backward-compatible default."""
    try:
        return ExecutionMode(str(execution_mode).strip().lower())
    except ValueError:
        return ExecutionMode.INSTANT


@router.get("", response_model=AnalysisResponse)
async def get_analysis(
    request: Request,
    force_refresh: bool = Query(False, description="Force fresh data fetch"),
    test_mode: bool = Query(False, description="Run in test mode (limited data)"),
    strategy: str = Query("balanced", description="Trading strategy (safe_steady, balanced, aggressive)"),
    execution_mode: str = Query("instant", description="Execution mode (instant, patient)"),
    # Legacy parameters for backward compatibility
    profit_weight: float = Query(1.0, ge=0.0, le=10.0, description="Deprecated: Profit weight"),
    volume_weight: float = Query(1.2, ge=0.0, le=10.0, description="Deprecated: Volume weight")
) -> AnalysisResponse:
    """Get analysis results with strategy-based scoring.

    If no recent analysis exists or force_refresh is True, runs a new analysis.
    Otherwise returns the latest cached analysis.

    Available strategies:
    - safe_steady: Low risk, prioritizes stable profits
    - balanced: Equal consideration of all factors
    - aggressive: High risk tolerance, prioritizes ROI and trends
    """
    logger = get_logger()
    logger.info(f"Analysis request received from {request.client.host if request.client else 'unknown'}")
    logger.info(
        "Request params: force_refresh=%s, test_mode=%s, strategy=%s, execution_mode=%s",
        force_refresh,
        test_mode,
        strategy,
        execution_mode,
    )

    # Parse strategy
    try:
        strategy_type = StrategyType(strategy)
    except ValueError:
        strategy_type = StrategyType.BALANCED
        logger.warning(f"Invalid strategy '{strategy}', defaulting to balanced")

    execution_mode_type = _parse_execution_mode(execution_mode)
    if execution_mode_type.value != str(execution_mode).strip().lower():
        logger.warning(f"Invalid execution_mode '{execution_mode}', defaulting to instant")

    service = get_analysis_service()

    try:
        if not force_refresh and not test_mode:
            latest = await service.get_latest_analysis()
            if latest is not None:
                latest_strategy = str(getattr(latest.strategy, "value", latest.strategy)).strip().lower()
                latest_execution_mode = str(getattr(latest.execution_mode, "value", latest.execution_mode)).strip().lower()

                if (
                    latest_strategy == strategy_type.value
                    and latest_execution_mode == execution_mode_type.value
                ):
                    logger.info(
                        "Returning latest background analysis run_id=%s",
                        latest.run_id,
                    )
                    return latest

                logger.info(
                    "Latest analysis run_id=%s params do not match request "
                    "(cached strategy=%s, cached execution_mode=%s, requested strategy=%s, requested execution_mode=%s); "
                    "running analysis for requested params",
                    latest.run_id,
                    latest_strategy,
                    latest_execution_mode,
                    strategy_type.value,
                    execution_mode_type.value,
                )
            else:
                status = service.get_status()
                if status["status"] == "running":
                    raise HTTPException(
                        status_code=404,
                        detail="No completed analysis available yet. Background polling is still running."
                    )

        # Explicit refresh/test-mode still supports on-demand runs.
        result = await service.run_full_analysis(
            strategy=strategy_type,
            execution_mode=execution_mode_type,
            force_refresh=force_refresh,
            test_mode=test_mode
        )
        logger.info(f"Analysis completed successfully, returning {result.total_sets} sets")
        return result
    except HTTPException:
        raise
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

    # Convert schema strategy to core strategy
    try:
        strategy_type = StrategyType(config.strategy.value)
    except (ValueError, AttributeError):
        strategy_type = StrategyType.BALANCED

    try:
        raw_execution_mode = getattr(config.execution_mode, "value", config.execution_mode)
        execution_mode_type = ExecutionMode(str(raw_execution_mode).strip().lower())
    except (ValueError, TypeError):
        execution_mode_type = ExecutionMode.INSTANT

    # Start background analysis
    async def run_analysis():
        try:
            await service.run_full_analysis(
                strategy=strategy_type,
                execution_mode=execution_mode_type,
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
    Connection stays open for live updates across continuous background polling
    until the client disconnects.
    """
    service = get_analysis_service()

    async def event_generator():
        """Generate SSE events for analysis progress."""
        last_payload: Optional[str] = None
        yield "retry: 1000\n\n"

        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                break

            status = service.get_status()
            payload = json.dumps({
                "status": status["status"],
                "progress": status["progress"],
                "message": status["message"],
                "run_id": status["run_id"],
                "error": status.get("error")
            })

            if payload != last_payload:
                yield f"data: {payload}\n\n"
                last_payload = payload
            else:
                # Keep the stream active through proxies when status is unchanged.
                yield ": ping\n\n"

            wait_for_update = getattr(service, "wait_for_status_update", None)
            if callable(wait_for_update):
                try:
                    await wait_for_update(timeout=1.0)
                    continue
                except Exception:
                    pass

            await asyncio.sleep(1.0)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable reverse-proxy buffering
        }
    )


@router.post("/rescore")
async def rescore_analysis(
    strategy: str = Query("balanced", description="Trading strategy (safe_steady, balanced, aggressive)"),
    execution_mode: str = Query("instant", description="Execution mode (instant, patient)"),
    # Legacy parameters for backward compatibility
    profit_weight: float = Query(1.0, ge=0.0, le=10.0, description="Deprecated"),
    volume_weight: float = Query(1.2, ge=0.0, le=10.0, description="Deprecated")
):
    """Rescore existing analysis data with a new strategy.

    Does not fetch new data, just recalculates scores based on the selected strategy.

    Available strategies:
    - safe_steady: Low risk, prioritizes stable profits
    - balanced: Equal consideration of all factors
    - aggressive: High risk tolerance, prioritizes ROI and trends
    """
    # Parse strategy
    try:
        strategy_type = StrategyType(strategy)
    except ValueError:
        strategy_type = StrategyType.BALANCED

    execution_mode_type = _parse_execution_mode(execution_mode)

    service = get_analysis_service()

    result = await service.recalculate_scores(
        strategy=strategy_type,
        execution_mode=execution_mode_type
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="No analysis data available. Run an analysis first."
        )

    # Convert to response format
    scored_models = [ScoredData(**item) for item in result]
    profitable_count = len([s for s in scored_models if s.profit_margin > 0])

    return {
        "sets": scored_models,
        "total_sets": len(scored_models),
        "profitable_sets": profitable_count,
        "strategy": strategy_type.value,
        "execution_mode": execution_mode_type.value,
        "weights": WeightsConfig(
            strategy=SchemaStrategyType(strategy_type.value),
            profit_weight=1.0,
            volume_weight=1.2
        )
    }


@router.get("/strategies", response_model=List[StrategyProfileResponse])
async def get_strategies() -> List[StrategyProfileResponse]:
    """Get all available trading strategies.

    Returns a list of strategy profiles with their configurations.
    """
    service = get_analysis_service()
    strategies = service.get_available_strategies()

    return [
        StrategyProfileResponse(
            type=SchemaStrategyType(s['type']),
            name=s['name'],
            description=s['description'],
            volatility_weight=s['volatility_weight'],
            trend_weight=s['trend_weight'],
            roi_weight=s['roi_weight'],
            min_volume_threshold=s['min_volume_threshold']
        )
        for s in strategies
    ]
