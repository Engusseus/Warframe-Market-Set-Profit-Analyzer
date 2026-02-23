"""History API routes."""
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from ...db.database import get_database_instance
from ...models.schemas import (
    AnalysisResponse,
    ExecutionMode,
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
        paginated_runs = await db.get_run_summary_page(limit=page_size, offset=offset)

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

        raw_execution_mode = analysis_data.get('execution_mode', 'instant')
        try:
            run_execution_mode = ExecutionMode(str(raw_execution_mode).strip().lower())
        except ValueError:
            run_execution_mode = ExecutionMode.INSTANT

        # Convert to ScoredData models with safe defaults for older historical rows
        scored_sets = []
        for s in analysis_data.get('sets', []):
            row_execution_mode = s.get('execution_mode', run_execution_mode.value)
            try:
                parsed_row_mode = ExecutionMode(str(row_execution_mode).strip().lower())
            except ValueError:
                parsed_row_mode = run_execution_mode

            scored_sets.append(ScoredData(
                set_slug=s.get('set_slug', ''),
                set_name=s.get('set_name', ''),
                set_price=s.get('set_price', 0.0),
                part_cost=s.get('part_cost', 0.0),
                profit_margin=s.get('profit_margin', 0.0),
                profit_percentage=s.get('profit_percentage', 0.0),
                instant_set_price=s.get('instant_set_price'),
                instant_part_cost=s.get('instant_part_cost'),
                instant_profit_margin=s.get('instant_profit_margin'),
                instant_profit_percentage=s.get('instant_profit_percentage'),
                patient_set_price=s.get('patient_set_price'),
                patient_part_cost=s.get('patient_part_cost'),
                patient_profit_margin=s.get('patient_profit_margin'),
                patient_profit_percentage=s.get('patient_profit_percentage'),
                part_details=s.get('part_details', []),
                execution_mode=parsed_row_mode,
                volume=s.get('volume', 0),
                normalized_profit=s.get('normalized_profit', 0.0),
                normalized_volume=s.get('normalized_volume', 0.0),
                profit_score=s.get('profit_score', 0.0),
                volume_score=s.get('volume_score', 0.0),
                total_score=s.get('total_score', 0.0),
                trend_slope=s.get('trend_slope', 0.0),
                trend_multiplier=s.get('trend_multiplier', 1.0),
                trend_direction=s.get('trend_direction', 'stable'),
                volatility=s.get('volatility', 0.0),
                volatility_penalty=s.get('volatility_penalty', 1.0),
                risk_level=s.get('risk_level', 'Medium'),
                composite_score=s.get('composite_score', s.get('total_score', 0.0)),
                profit_contribution=s.get('profit_contribution', 0.0),
                volume_contribution=s.get('volume_contribution', 0.0),
                trend_contribution=s.get('trend_contribution', 1.0),
                volatility_contribution=s.get('volatility_contribution', 1.0),
                bid_ask_ratio=s.get('bid_ask_ratio', 0.0),
                sell_side_competition=s.get('sell_side_competition', 0.0),
                liquidity_velocity=s.get('liquidity_velocity', 0.0),
                liquidity_multiplier=s.get('liquidity_multiplier', 1.0),
            ))

        # Parse timestamp from date_string
        date_string = analysis_data.get('date_string', '')
        try:
            timestamp = datetime.strptime(date_string, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            timestamp = datetime.fromtimestamp(analysis_data.get('timestamp', 0))

        weights_data = analysis_data.get('weights', {})

        return AnalysisResponse(
            run_id=analysis_data['run_id'],
            timestamp=timestamp,
            sets=scored_sets,
            total_sets=analysis_data.get('total_sets', len(scored_sets)),
            profitable_sets=analysis_data.get(
                'profitable_sets',
                len([s for s in scored_sets if s.profit_margin > 0])
            ),
            weights=WeightsConfig(
                profit_weight=weights_data.get('profit_weight', 1.0),
                volume_weight=weights_data.get('volume_weight', 1.2),
                strategy=weights_data.get('strategy', 'balanced')
            ),
            strategy=analysis_data.get('strategy', 'balanced'),
            execution_mode=run_execution_mode,
            cached=True  # Historical data is essentially cached
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
