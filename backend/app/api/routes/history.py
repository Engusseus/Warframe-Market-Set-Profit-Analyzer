"""History API routes."""
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from ...db.database import get_database_instance
from ...models.schemas import (
    AnalysisResponse,
    HistoryResponse,
    HistoryRun,
    RunDetailResponse,
    ScoredData,
    WeightsConfig,
)

router = APIRouter()


@router.get("", response_model=HistoryResponse)
async def get_history(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page")
) -> HistoryResponse:
    """Get paginated list of historical market runs."""
    db = await get_database_instance()

    try:
        # Get total count
        total_runs = await db.get_run_count()

        # Calculate offset
        offset = (page - 1) * page_size

        # Get run summaries
        runs = await db.get_run_summary(limit=page_size + offset)

        # Apply pagination
        paginated_runs = runs[offset:offset + page_size] if offset < len(runs) else []

        # Convert to response models
        history_runs = [
            HistoryRun(
                run_id=r['run_id'],
                date_string=r['date_string'],
                set_count=r['set_count'] or 0,
                avg_profit=r['avg_profit'],
                max_profit=r['max_profit']
            )
            for r in paginated_runs
        ]

        return HistoryResponse(
            runs=history_runs,
            total_runs=total_runs,
            page=page,
            page_size=page_size
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{run_id}", response_model=RunDetailResponse)
async def get_run_detail(run_id: int) -> RunDetailResponse:
    """Get detailed data for a specific market run."""
    db = await get_database_instance()

    try:
        run_data = await db.get_run_by_id(run_id)

        if run_data is None:
            raise HTTPException(status_code=404, detail="Run not found")

        set_profits = run_data.get('set_profits', [])

        # Calculate summary
        summary = {
            'total_sets': len(set_profits),
            'average_profit': sum(s['profit_margin'] for s in set_profits) / len(set_profits) if set_profits else 0,
            'max_profit': max((s['profit_margin'] for s in set_profits), default=0),
            'min_profit': min((s['profit_margin'] for s in set_profits), default=0),
            'profitable_sets': len([s for s in set_profits if s['profit_margin'] > 0])
        }

        return RunDetailResponse(
            run_id=run_data['run_id'],
            date_string=run_data['date_string'],
            timestamp=run_data['timestamp'],
            sets=set_profits,
            summary=summary
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{run_id}/analysis", response_model=AnalysisResponse)
async def get_run_analysis(run_id: int) -> AnalysisResponse:
    """Get full analysis data for a historical run.

    Returns the complete scored analysis data that can be loaded
    into the Analysis tab for review.
    """
    db = await get_database_instance()

    try:
        analysis_data = await db.get_full_analysis(run_id)

        if analysis_data is None:
            raise HTTPException(
                status_code=404,
                detail="Full analysis data not found for this run. Only runs created after this feature was added have full data stored."
            )

        # Convert to ScoredData models
        scored_sets = [
            ScoredData(
                set_slug=s['set_slug'],
                set_name=s['set_name'],
                set_price=s['set_price'],
                part_cost=s['part_cost'],
                profit_margin=s['profit_margin'],
                profit_percentage=s['profit_percentage'],
                part_details=s['part_details'],
                volume=s['volume'],
                normalized_profit=s['normalized_profit'],
                normalized_volume=s['normalized_volume'],
                profit_score=s['profit_score'],
                volume_score=s['volume_score'],
                total_score=s['total_score']
            )
            for s in analysis_data['sets']
        ]

        # Parse timestamp from date_string
        timestamp = datetime.strptime(analysis_data['date_string'], '%Y-%m-%d %H:%M:%S')

        return AnalysisResponse(
            run_id=analysis_data['run_id'],
            timestamp=timestamp,
            sets=scored_sets,
            total_sets=analysis_data['total_sets'],
            profitable_sets=analysis_data['profitable_sets'],
            weights=WeightsConfig(
                profit_weight=analysis_data['weights']['profit_weight'],
                volume_weight=analysis_data['weights']['volume_weight']
            ),
            cached=True  # Historical data is essentially cached
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
