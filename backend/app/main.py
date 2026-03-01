"""FastAPI application entry point."""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.router import api_router
from .config import get_settings
from .core.logging import setup_logging, get_logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""
    # Startup
    settings = get_settings()
    logger = setup_logging()
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"CORS origins: {settings.cors_origins}")
    from .api.routes.analysis import get_analysis_service

    analysis_service = get_analysis_service()
    polling_enabled = os.environ.get("PYTEST_CURRENT_TEST") is None
    poll_interval_raw = os.environ.get("ANALYSIS_POLL_INTERVAL_SECONDS")
    poll_interval = None
    if poll_interval_raw:
        try:
            poll_interval = float(poll_interval_raw)
        except ValueError:
            logger.warning(
                "Invalid ANALYSIS_POLL_INTERVAL_SECONDS=%r, using default",
                poll_interval_raw,
            )

    if polling_enabled:
        try:
            await analysis_service.start_continuous_polling(
                poll_interval_seconds=poll_interval,
                force_refresh=False,
            )
            logger.info("Continuous analysis polling started")
        except Exception as e:
            logger.warning(f"Failed to start continuous analysis polling: {e}")
    else:
        logger.info("Continuous analysis polling disabled in pytest runtime")

    try:
        yield
    finally:
        # Shutdown
        logger = get_logger()
        logger.info("Shutting down...")
        try:
            await analysis_service.close()
        except Exception as e:
            logger.warning(f"Error during analysis service shutdown: {e}")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="API for analyzing Warframe Market Prime set profitability",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API router
    app.include_router(api_router, prefix=settings.api_prefix)

    # Root endpoint
    @app.get("/")
    async def root():
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
            "api": settings.api_prefix
        }

    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000
    )
