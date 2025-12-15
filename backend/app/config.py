"""Application configuration."""
import os
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # Application
    app_name: str = "Warframe Market Analyzer"
    app_version: str = "2.0.0"
    debug: bool = False

    # API
    api_prefix: str = "/api"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Warframe Market API
    warframe_market_base_url: str = "https://api.warframe.market"
    warframe_market_v1_url: str = "https://api.warframe.market/v1"
    warframe_market_v2_url: str = "https://api.warframe.market/v2"

    # Rate limiting
    rate_limit_requests: int = 3
    rate_limit_window: float = 1.0

    # Database
    database_path: str = "cache/market_runs.sqlite"

    # Cache
    cache_dir: str = "cache"
    cache_file: str = "prime_sets_cache.json"

    # Timeouts
    request_timeout: int = 10
    analysis_timeout: int = 600  # 10 minutes max for full analysis

    # Default weights
    default_profit_weight: float = 1.0
    default_volume_weight: float = 1.2

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Export commonly used paths
def get_database_path() -> str:
    """Get absolute database path."""
    settings = get_settings()
    return os.path.abspath(settings.database_path)


def get_cache_dir() -> str:
    """Get absolute cache directory path."""
    settings = get_settings()
    return os.path.abspath(settings.cache_dir)
