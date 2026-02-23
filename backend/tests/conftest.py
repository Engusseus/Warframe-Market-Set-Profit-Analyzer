"""Shared pytest fixtures for backend tests."""
import asyncio
import os
import tempfile
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import create_app
from app.config import Settings, get_settings
from app.db.database import AsyncMarketDatabase
from app.core.rate_limiter import RateLimiter
from app.core.strategy_profiles import StrategyType


# === Test Settings ===

def get_test_settings() -> Settings:
    """Create test-specific settings."""
    return Settings(
        debug=True,
        database_path=":memory:",
        cors_origins=["http://localhost:5173", "http://testserver"],
    )


# === Event Loop ===

@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# === Database Fixtures ===

@pytest.fixture
def temp_db_path() -> Generator[str, None, None]:
    """Create a temporary database file for isolated tests."""
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
        db_path = f.name
    yield db_path
    try:
        os.unlink(db_path)
    except FileNotFoundError:
        pass


@pytest_asyncio.fixture
async def test_database(temp_db_path: str) -> AsyncGenerator[AsyncMarketDatabase, None]:
    """Provide an isolated test database."""
    db = AsyncMarketDatabase(db_path=temp_db_path)
    await db._ensure_initialized()
    yield db
    await db.close()


# === Application Fixtures ===

@pytest.fixture
def test_app():
    """Create a test FastAPI application."""
    app = create_app()
    app.dependency_overrides[get_settings] = get_test_settings
    return app


@pytest_asyncio.fixture
async def async_client(test_app) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client for API testing."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


# === Utility Fixtures ===

@pytest.fixture
def rate_limiter() -> RateLimiter:
    """Create a fast rate limiter for testing."""
    return RateLimiter(max_requests=100, time_window=0.01)


# === Sample Data Fixtures ===

@pytest.fixture
def sample_profit_data() -> list:
    """Sample profit data for testing scoring functions."""
    return [
        {
            "set_slug": "saryn_prime_set",
            "set_name": "Saryn Prime Set",
            "set_price": 150.0,
            "part_cost": 100.0,
            "profit_margin": 50.0,
            "profit_percentage": 50.0,
            "instant_set_price": 130.0,
            "instant_part_cost": 100.0,
            "instant_profit_margin": 30.0,
            "instant_profit_percentage": 30.0,
            "patient_set_price": 150.0,
            "patient_part_cost": 80.0,
            "patient_profit_margin": 70.0,
            "patient_profit_percentage": 87.5,
            "set_lowest_price": 150.0,
            "set_highest_bid": 130.0,
            "set_top_sell_orders": [
                {"platinum": 150.0, "quantity": 3},
                {"platinum": 152.0, "quantity": 2},
            ],
            "set_top_buy_orders": [
                {"platinum": 130.0, "quantity": 4},
                {"platinum": 128.0, "quantity": 3},
            ],
            "part_details": [],
        },
        {
            "set_slug": "mesa_prime_set",
            "set_name": "Mesa Prime Set",
            "set_price": 200.0,
            "part_cost": 180.0,
            "profit_margin": 20.0,
            "profit_percentage": 11.1,
            "instant_set_price": 175.0,
            "instant_part_cost": 180.0,
            "instant_profit_margin": -5.0,
            "instant_profit_percentage": -2.78,
            "patient_set_price": 200.0,
            "patient_part_cost": 150.0,
            "patient_profit_margin": 50.0,
            "patient_profit_percentage": 33.33,
            "set_lowest_price": 200.0,
            "set_highest_bid": 175.0,
            "set_top_sell_orders": [
                {"platinum": 200.0, "quantity": 6},
                {"platinum": 205.0, "quantity": 4},
            ],
            "set_top_buy_orders": [
                {"platinum": 175.0, "quantity": 2},
                {"platinum": 172.0, "quantity": 2},
            ],
            "part_details": [],
        },
        {
            "set_slug": "volt_prime_set",
            "set_name": "Volt Prime Set",
            "set_price": 80.0,
            "part_cost": 60.0,
            "profit_margin": 20.0,
            "profit_percentage": 33.3,
            "instant_set_price": 70.0,
            "instant_part_cost": 60.0,
            "instant_profit_margin": 10.0,
            "instant_profit_percentage": 16.67,
            "patient_set_price": 80.0,
            "patient_part_cost": 55.0,
            "patient_profit_margin": 25.0,
            "patient_profit_percentage": 45.45,
            "set_lowest_price": 80.0,
            "set_highest_bid": 70.0,
            "set_top_sell_orders": [
                {"platinum": 80.0, "quantity": 2},
            ],
            "set_top_buy_orders": [
                {"platinum": 70.0, "quantity": 5},
                {"platinum": 68.0, "quantity": 3},
            ],
            "part_details": [],
        },
    ]


@pytest.fixture
def sample_volume_data() -> dict:
    """Sample volume data for testing scoring functions."""
    return {
        "individual": {
            "saryn_prime_set": 150,
            "mesa_prime_set": 300,
            "volt_prime_set": 50,
        },
        "total": 500,
    }


@pytest.fixture
def sample_trend_metrics() -> dict:
    """Sample trend/volatility metrics for testing."""
    return {
        "saryn_prime_set": {
            "trend_slope": 0.5,
            "trend_multiplier": 1.1,
            "trend_direction": "rising",
            "volatility": 0.15,
            "volatility_penalty": 1.3,
            "risk_level": "Medium",
            "data_points": 7,
        },
        "mesa_prime_set": {
            "trend_slope": -0.2,
            "trend_multiplier": 0.9,
            "trend_direction": "falling",
            "volatility": 0.05,
            "volatility_penalty": 1.1,
            "risk_level": "Low",
            "data_points": 7,
        },
        "volt_prime_set": {
            "trend_slope": 0.0,
            "trend_multiplier": 1.0,
            "trend_direction": "stable",
            "volatility": 0.25,
            "volatility_penalty": 1.5,
            "risk_level": "High",
            "data_points": 7,
        },
    }


@pytest.fixture
def sample_set_prices() -> list:
    """Sample set prices for profit calculation tests."""
    return [
        {
            "slug": "saryn_prime_set",
            "lowest_price": 150.0,
            "highest_bid": 130.0,
            "top_sell_orders": [
                {"platinum": 150.0, "quantity": 1},
                {"platinum": 152.0, "quantity": 3},
            ],
            "top_buy_orders": [
                {"platinum": 130.0, "quantity": 1},
                {"platinum": 128.0, "quantity": 2},
            ],
        },
        {
            "slug": "mesa_prime_set",
            "lowest_price": 200.0,
            "highest_bid": 175.0,
            "top_sell_orders": [
                {"platinum": 200.0, "quantity": 2},
                {"platinum": 205.0, "quantity": 2},
            ],
            "top_buy_orders": [
                {"platinum": 175.0, "quantity": 1},
                {"platinum": 172.0, "quantity": 4},
            ],
        },
        {
            "slug": "volt_prime_set",
            "lowest_price": 80.0,
            "highest_bid": 70.0,
            "top_sell_orders": [
                {"platinum": 80.0, "quantity": 3},
            ],
            "top_buy_orders": [
                {"platinum": 70.0, "quantity": 2},
            ],
        },
    ]


@pytest.fixture
def sample_part_prices() -> list:
    """Sample part prices for profit calculation tests."""
    return [
        {
            "slug": "saryn_prime_blueprint",
            "lowest_price": 25.0,
            "highest_bid": 20.0,
            "quantity_in_set": 1,
            "top_sell_orders": [
                {"platinum": 25.0, "quantity": 2},
                {"platinum": 26.0, "quantity": 4},
            ],
            "top_buy_orders": [
                {"platinum": 20.0, "quantity": 2},
                {"platinum": 19.0, "quantity": 5},
            ],
        },
        {
            "slug": "saryn_prime_chassis",
            "lowest_price": 25.0,
            "highest_bid": 20.0,
            "quantity_in_set": 1,
            "top_sell_orders": [
                {"platinum": 25.0, "quantity": 3},
                {"platinum": 26.0, "quantity": 2},
            ],
            "top_buy_orders": [
                {"platinum": 20.0, "quantity": 1},
                {"platinum": 19.0, "quantity": 4},
            ],
        },
        {
            "slug": "saryn_prime_neuroptics",
            "lowest_price": 25.0,
            "highest_bid": 20.0,
            "quantity_in_set": 1,
            "top_sell_orders": [
                {"platinum": 25.0, "quantity": 2},
                {"platinum": 27.0, "quantity": 5},
            ],
            "top_buy_orders": [
                {"platinum": 20.0, "quantity": 3},
                {"platinum": 18.0, "quantity": 6},
            ],
        },
        {
            "slug": "saryn_prime_systems",
            "lowest_price": 25.0,
            "highest_bid": 20.0,
            "quantity_in_set": 1,
            "top_sell_orders": [
                {"platinum": 25.0, "quantity": 1},
                {"platinum": 28.0, "quantity": 3},
            ],
            "top_buy_orders": [
                {"platinum": 20.0, "quantity": 2},
                {"platinum": 17.0, "quantity": 7},
            ],
        },
        {
            "slug": "mesa_prime_blueprint",
            "lowest_price": 45.0,
            "highest_bid": 38.0,
            "quantity_in_set": 1,
            "top_sell_orders": [
                {"platinum": 45.0, "quantity": 2},
                {"platinum": 46.0, "quantity": 3},
            ],
            "top_buy_orders": [
                {"platinum": 38.0, "quantity": 2},
                {"platinum": 37.0, "quantity": 4},
            ],
        },
        {
            "slug": "mesa_prime_chassis",
            "lowest_price": 45.0,
            "highest_bid": 38.0,
            "quantity_in_set": 1,
            "top_sell_orders": [
                {"platinum": 45.0, "quantity": 3},
                {"platinum": 47.0, "quantity": 5},
            ],
            "top_buy_orders": [
                {"platinum": 38.0, "quantity": 1},
                {"platinum": 36.0, "quantity": 4},
            ],
        },
        {
            "slug": "mesa_prime_neuroptics",
            "lowest_price": 45.0,
            "highest_bid": 38.0,
            "quantity_in_set": 1,
            "top_sell_orders": [
                {"platinum": 45.0, "quantity": 2},
                {"platinum": 47.0, "quantity": 2},
            ],
            "top_buy_orders": [
                {"platinum": 38.0, "quantity": 3},
                {"platinum": 35.0, "quantity": 4},
            ],
        },
        {
            "slug": "mesa_prime_systems",
            "lowest_price": 45.0,
            "highest_bid": 38.0,
            "quantity_in_set": 1,
            "top_sell_orders": [
                {"platinum": 45.0, "quantity": 2},
                {"platinum": 48.0, "quantity": 4},
            ],
            "top_buy_orders": [
                {"platinum": 38.0, "quantity": 2},
                {"platinum": 36.0, "quantity": 3},
            ],
        },
    ]


@pytest.fixture
def sample_detailed_sets() -> list:
    """Sample detailed set data for profit calculation tests."""
    return [
        {
            "id": "saryn_prime_set",
            "slug": "saryn_prime_set",
            "name": "Saryn Prime Set",
            "setParts": [
                {"code": "saryn_prime_blueprint", "name": "Saryn Prime Blueprint", "quantityInSet": 1},
                {"code": "saryn_prime_chassis", "name": "Saryn Prime Chassis", "quantityInSet": 1},
                {"code": "saryn_prime_neuroptics", "name": "Saryn Prime Neuroptics", "quantityInSet": 1},
                {"code": "saryn_prime_systems", "name": "Saryn Prime Systems", "quantityInSet": 1},
            ],
        },
        {
            "id": "mesa_prime_set",
            "slug": "mesa_prime_set",
            "name": "Mesa Prime Set",
            "setParts": [
                {"code": "mesa_prime_blueprint", "name": "Mesa Prime Blueprint", "quantityInSet": 1},
                {"code": "mesa_prime_chassis", "name": "Mesa Prime Chassis", "quantityInSet": 1},
                {"code": "mesa_prime_neuroptics", "name": "Mesa Prime Neuroptics", "quantityInSet": 1},
                {"code": "mesa_prime_systems", "name": "Mesa Prime Systems", "quantityInSet": 1},
            ],
        },
    ]


@pytest.fixture
def sample_price_history() -> list:
    """Sample price history data for trend calculation tests."""
    base_timestamp = 1700000000
    day_seconds = 86400
    return [
        {"lowest_price": 100.0, "timestamp": base_timestamp},
        {"lowest_price": 105.0, "timestamp": base_timestamp + day_seconds},
        {"lowest_price": 102.0, "timestamp": base_timestamp + 2 * day_seconds},
        {"lowest_price": 110.0, "timestamp": base_timestamp + 3 * day_seconds},
        {"lowest_price": 108.0, "timestamp": base_timestamp + 4 * day_seconds},
        {"lowest_price": 115.0, "timestamp": base_timestamp + 5 * day_seconds},
        {"lowest_price": 120.0, "timestamp": base_timestamp + 6 * day_seconds},
    ]


@pytest.fixture
def sample_scored_data() -> list:
    """Sample scored data for rescore tests."""
    return [
        {
            "set_slug": "saryn_prime_set",
            "set_name": "Saryn Prime Set",
            "set_price": 150.0,
            "part_cost": 100.0,
            "profit_margin": 50.0,
            "profit_percentage": 50.0,
            "instant_set_price": 130.0,
            "instant_part_cost": 100.0,
            "instant_profit_margin": 30.0,
            "instant_profit_percentage": 30.0,
            "patient_set_price": 150.0,
            "patient_part_cost": 80.0,
            "patient_profit_margin": 70.0,
            "patient_profit_percentage": 87.5,
            "volume": 150,
            "trend_multiplier": 1.1,
            "volatility_penalty": 1.3,
            "composite_score": 100.0,
            "liquidity_multiplier": 1.1,
            "bid_ask_ratio": 0.87,
            "sell_side_competition": 0.6,
            "liquidity_velocity": 1.45,
        },
        {
            "set_slug": "mesa_prime_set",
            "set_name": "Mesa Prime Set",
            "set_price": 200.0,
            "part_cost": 180.0,
            "profit_margin": 20.0,
            "profit_percentage": 11.1,
            "instant_set_price": 175.0,
            "instant_part_cost": 180.0,
            "instant_profit_margin": -5.0,
            "instant_profit_percentage": -2.78,
            "patient_set_price": 200.0,
            "patient_part_cost": 150.0,
            "patient_profit_margin": 50.0,
            "patient_profit_percentage": 33.33,
            "volume": 300,
            "trend_multiplier": 0.9,
            "volatility_penalty": 1.1,
            "composite_score": 50.0,
            "liquidity_multiplier": 0.9,
            "bid_ask_ratio": 0.88,
            "sell_side_competition": 1.8,
            "liquidity_velocity": 0.49,
        },
    ]
