"""Main API router aggregating all route modules."""
from fastapi import APIRouter

from .routes import analysis, history, sets, stats, export

# Create main API router
api_router = APIRouter()

# Include all route modules
api_router.include_router(
    analysis.router,
    prefix="/analysis",
    tags=["Analysis"]
)

api_router.include_router(
    history.router,
    prefix="/history",
    tags=["History"]
)

api_router.include_router(
    sets.router,
    prefix="/sets",
    tags=["Sets"]
)

api_router.include_router(
    stats.router,
    prefix="/stats",
    tags=["Statistics"]
)

api_router.include_router(
    export.router,
    prefix="/export",
    tags=["Export"]
)
