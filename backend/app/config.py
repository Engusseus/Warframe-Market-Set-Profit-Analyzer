"""Application configuration."""
import os
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings

LOCAL_ENVIRONMENT = "local"
LOCAL_SQLITE_FALLBACK_URL = "sqlite:///./local.db"


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # Application
    app_name: str = "Warframe Market Analyzer"
    app_version: str = "2.0.0"
    debug: bool = False
    environment: str = "production"

    # API
    api_prefix: str = "/api"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "http://localhost:80",
        "http://localhost",
    ]

    # Warframe Market API
    warframe_market_base_url: str = "https://api.warframe.market"
    warframe_market_v1_url: str = "https://api.warframe.market/v1"
    warframe_market_v2_url: str = "https://api.warframe.market/v2"

    # Rate limiting
    rate_limit_requests: int = 3
    rate_limit_window: float = 1.0

    # Database
    database_path: str = "cache/market_runs.sqlite"
    database_url: Optional[str] = None

    # Cache
    cache_dir: str = "cache"
    cache_file: str = "prime_sets_cache.json"
    cache_backend: Optional[str] = None
    cache_lru_max_entries: int = 128

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

    def is_local_environment(self) -> bool:
        """Check whether runtime is configured for local mode."""
        return self.environment.lower() == LOCAL_ENVIRONMENT

    def get_database_target(self) -> str:
        """Get database path/URL for current environment."""
        if self.is_local_environment():
            # In local mode we always avoid external DB dependencies.
            if self.database_url and self.database_url.startswith("sqlite:///"):
                return self.database_url
            if self.database_path.startswith("sqlite:///"):
                return self.database_path
            if self.database_path not in {"cache/market_runs.sqlite", "cache/market_runs.db"}:
                return self.database_path
            return LOCAL_SQLITE_FALLBACK_URL
        if self.database_url:
            return self.database_url
        return self.database_path

    def get_cache_backend(self) -> str:
        """Get configured cache backend with local fallback behavior."""
        if self.is_local_environment():
            return "memory"
        if self.cache_backend:
            return self.cache_backend.lower()
        return "file"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Export commonly used paths
def get_database_path() -> str:
    """Get absolute database path."""
    settings = get_settings()
    database_target = settings.get_database_target()
    if database_target == ":memory:":
        return database_target
    if database_target.startswith("sqlite:///"):
        database_target = database_target.replace("sqlite:///", "", 1)
    return os.path.abspath(database_target)


def get_cache_dir() -> str:
    """Get absolute cache directory path."""
    settings = get_settings()
    return os.path.abspath(settings.cache_dir)
