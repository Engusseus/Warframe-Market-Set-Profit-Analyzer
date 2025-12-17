"""Statistics API routes."""
from fastapi import APIRouter, HTTPException

from ...config import get_settings
from ...core.cache_manager import CacheManager
from ...db.database import get_database_instance
from ...models.schemas import AnalysisStats, DatabaseStats, StatsResponse

router = APIRouter()


@router.get("", response_model=StatsResponse)
async def get_stats() -> StatsResponse:
    """Get database and analysis statistics."""
    db = await get_database_instance()
    settings = get_settings()
    cache_manager = CacheManager(settings.cache_dir)

    try:
        # Get database stats
        db_stats = await db.get_database_stats()

        # Get cache age
        cache_age = cache_manager.get_cache_age()

        # Build response
        database_stats = DatabaseStats(
            total_runs=db_stats['total_runs'],
            total_profit_records=db_stats['total_profit_records'],
            database_size_bytes=db_stats['database_size_bytes'],
            first_run=db_stats.get('first_run'),
            last_run=db_stats.get('last_run'),
            time_span_days=db_stats.get('time_span_days')
        )

        # Get cached set count
        detailed_sets = cache_manager.get_detailed_sets()
        total_sets = len(detailed_sets) if detailed_sets else None

        analysis_stats = AnalysisStats(
            cache_age_seconds=cache_age,
            last_analysis=db_stats.get('last_run'),
            total_prime_sets=total_sets
        )

        return StatsResponse(
            database=database_stats,
            analysis=analysis_stats
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "Warframe Market Analyzer API",
        "version": get_settings().app_version
    }
