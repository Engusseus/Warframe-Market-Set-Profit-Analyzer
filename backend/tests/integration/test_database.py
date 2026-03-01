"""Integration tests for database operations."""
import pytest
import pytest_asyncio
import time

from app.db.database import AsyncMarketDatabase


class TestAsyncMarketDatabaseInit:
    """Tests for database initialization."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_creates_tables_on_init(self, test_database):
        """Test that tables are created on initialization."""
        # Tables should exist after initialization
        async with test_database._lock:
            import sqlite3
            conn = sqlite3.connect(test_database.db_path)
            try:
                # Check market_runs table
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='market_runs'"
                )
                assert cursor.fetchone() is not None

                # Check set_profits table
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='set_profits'"
                )
                assert cursor.fetchone() is not None
            finally:
                conn.close()

    @pytest.mark.integration
    def test_raises_on_invalid_db_path(self):
        """Test that invalid db path raises error."""
        with pytest.raises(ValueError, match="must end with .sqlite"):
            AsyncMarketDatabase(db_path="/tmp/invalid.db")


class TestSaveMarketRun:
    """Tests for save_market_run method."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_saves_and_returns_run_id(self, test_database):
        """Test that market run is saved and run_id returned."""
        profit_data = [
            {"set_slug": "test_set", "set_name": "Test Set", "profit_margin": 50.0},
        ]
        set_prices = [{"slug": "test_set", "lowest_price": 100.0}]

        run_id = await test_database.save_market_run(profit_data, set_prices)

        assert run_id is not None
        assert run_id > 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_increments_run_count(self, test_database):
        """Test that run count increments with each save."""
        profit_data = [
            {"set_slug": "test_set", "set_name": "Test Set", "profit_margin": 50.0},
        ]
        set_prices = [{"slug": "test_set", "lowest_price": 100.0}]

        initial_count = await test_database.get_run_count()

        await test_database.save_market_run(profit_data, set_prices)
        await test_database.save_market_run(profit_data, set_prices)

        final_count = await test_database.get_run_count()
        assert final_count == initial_count + 2

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_raises_on_empty_profit_data(self, test_database):
        """Test that empty profit_data raises ValueError."""
        with pytest.raises(ValueError, match="profit_data cannot be empty"):
            await test_database.save_market_run([], [{"slug": "x", "lowest_price": 1}])

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_raises_on_empty_set_prices(self, test_database):
        """Test that empty set_prices raises ValueError."""
        with pytest.raises(ValueError, match="set_prices cannot be empty"):
            await test_database.save_market_run(
                [{"set_slug": "x", "set_name": "X", "profit_margin": 1}],
                []
            )

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_saves_multiple_sets(self, test_database):
        """Test that multiple sets are saved correctly."""
        profit_data = [
            {"set_slug": "set_a", "set_name": "Set A", "profit_margin": 50.0},
            {"set_slug": "set_b", "set_name": "Set B", "profit_margin": 30.0},
            {"set_slug": "set_c", "set_name": "Set C", "profit_margin": 10.0},
        ]
        set_prices = [
            {"slug": "set_a", "lowest_price": 150.0},
            {"slug": "set_b", "lowest_price": 130.0},
            {"slug": "set_c", "lowest_price": 110.0},
        ]

        run_id = await test_database.save_market_run(profit_data, set_prices)
        run_data = await test_database.get_run_by_id(run_id)

        assert len(run_data['set_profits']) == 3


class TestGetRunById:
    """Tests for get_run_by_id method."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_returns_saved_run_data(self, test_database):
        """Test that saved run data is retrieved correctly."""
        profit_data = [
            {"set_slug": "test_set", "set_name": "Test Set", "profit_margin": 50.0},
        ]
        set_prices = [{"slug": "test_set", "lowest_price": 100.0}]

        run_id = await test_database.save_market_run(profit_data, set_prices)
        run_data = await test_database.get_run_by_id(run_id)

        assert run_data is not None
        assert run_data['run_id'] == run_id
        assert len(run_data['set_profits']) == 1
        assert run_data['set_profits'][0]['set_slug'] == "test_set"
        assert run_data['set_profits'][0]['profit_margin'] == 50.0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_returns_none_for_invalid_id(self, test_database):
        """Test that invalid run_id returns None."""
        result = await test_database.get_run_by_id(99999)
        assert result is None


class TestGetRunSummary:
    """Tests for get_run_summary method."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_returns_limited_results(self, test_database):
        """Test that results are limited correctly."""
        profit_data = [
            {"set_slug": "test_set", "set_name": "Test Set", "profit_margin": 50.0},
        ]
        set_prices = [{"slug": "test_set", "lowest_price": 100.0}]

        # Create 5 runs
        for _ in range(5):
            await test_database.save_market_run(profit_data, set_prices)

        # Get only 3
        summary = await test_database.get_run_summary(limit=3)
        assert len(summary) == 3

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_includes_summary_fields(self, test_database):
        """Test that summary includes required fields."""
        profit_data = [
            {"set_slug": "set_a", "set_name": "Set A", "profit_margin": 50.0},
            {"set_slug": "set_b", "set_name": "Set B", "profit_margin": 30.0},
        ]
        set_prices = [
            {"slug": "set_a", "lowest_price": 150.0},
            {"slug": "set_b", "lowest_price": 130.0},
        ]

        await test_database.save_market_run(profit_data, set_prices)
        summary = await test_database.get_run_summary(limit=1)

        assert len(summary) == 1
        run = summary[0]
        assert 'run_id' in run
        assert 'date_string' in run
        assert 'set_count' in run
        assert 'avg_profit' in run
        assert 'max_profit' in run
        assert run['set_count'] == 2
        assert run['max_profit'] == 50.0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_raises_on_invalid_limit(self, test_database):
        """Test that invalid limit raises ValueError."""
        with pytest.raises(ValueError, match="limit must be positive"):
            await test_database.get_run_summary(limit=0)


class TestGetSetPriceHistory:
    """Tests for get_set_price_history method."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_returns_price_history(self, test_database):
        """Test that price history is returned."""
        profit_data = [
            {"set_slug": "tracked_set", "set_name": "Tracked Set", "profit_margin": 50.0},
        ]
        set_prices = [{"slug": "tracked_set", "lowest_price": 100.0}]

        await test_database.save_market_run(profit_data, set_prices)

        history = await test_database.get_set_price_history("tracked_set")
        assert len(history) >= 1
        assert history[0]['lowest_price'] == 100.0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_returns_empty_for_unknown_set(self, test_database):
        """Test that unknown set returns empty history."""
        history = await test_database.get_set_price_history("nonexistent_set")
        assert history == []

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_raises_on_empty_slug(self, test_database):
        """Test that empty slug raises ValueError."""
        with pytest.raises(ValueError, match="set_slug cannot be empty"):
            await test_database.get_set_price_history("")


class TestGetPriceHistoryBatch:
    """Tests for get_price_history_batch method."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_returns_batch_history(self, test_database):
        """Test that batch history is returned for multiple sets."""
        profit_data = [
            {"set_slug": "set_a", "set_name": "Set A", "profit_margin": 50.0},
            {"set_slug": "set_b", "set_name": "Set B", "profit_margin": 30.0},
        ]
        set_prices = [
            {"slug": "set_a", "lowest_price": 150.0},
            {"slug": "set_b", "lowest_price": 130.0},
        ]

        await test_database.save_market_run(profit_data, set_prices)

        result = await test_database.get_price_history_batch(["set_a", "set_b"])

        assert "set_a" in result
        assert "set_b" in result
        assert len(result["set_a"]) >= 1
        assert len(result["set_b"]) >= 1

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_returns_empty_dict_for_empty_input(self, test_database):
        """Test that empty input returns empty dict."""
        result = await test_database.get_price_history_batch([])
        assert result == {}


class TestGetLatestRunId:
    """Tests for get_latest_run_id method."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_returns_none_when_empty(self, test_database):
        """Test that None is returned when no runs exist."""
        result = await test_database.get_latest_run_id()
        assert result is None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_returns_most_recent(self, test_database):
        """Test that most recent run_id is returned."""
        profit_data = [
            {"set_slug": "test", "set_name": "Test", "profit_margin": 10.0},
        ]
        set_prices = [{"slug": "test", "lowest_price": 50.0}]

        run_id_1 = await test_database.save_market_run(profit_data, set_prices)
        run_id_2 = await test_database.save_market_run(profit_data, set_prices)

        latest = await test_database.get_latest_run_id()
        assert latest == run_id_2


class TestSaveFullAnalysis:
    """Tests for save_full_analysis method."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_saves_scored_data(self, test_database):
        """Test that scored data is saved correctly."""
        # First create a market run
        profit_data = [
            {"set_slug": "test_set", "set_name": "Test Set", "profit_margin": 50.0},
        ]
        set_prices = [{"slug": "test_set", "lowest_price": 100.0}]
        run_id = await test_database.save_market_run(profit_data, set_prices)

        # Now save full analysis
        scored_data = [
            {
                "set_slug": "test_set",
                "set_name": "Test Set",
                "set_price": 100.0,
                "part_cost": 50.0,
                "profit_margin": 50.0,
                "profit_percentage": 100.0,
                "volume": 150,
                "normalized_profit": 1.0,
                "normalized_volume": 0.5,
                "profit_score": 1.0,
                "volume_score": 0.6,
                "total_score": 1.6,
                "part_details": [],
                "composite_score": 150.0,
                "trend_multiplier": 1.1,
                "trend_direction": "rising",
                "volatility_penalty": 1.2,
                "risk_level": "Medium",
            }
        ]

        await test_database.save_full_analysis(
            run_id=run_id,
            scored_data=scored_data,
            strategy="balanced",
            execution_mode="patient",
        )

        # Retrieve and verify
        result = await test_database.get_full_analysis(run_id)
        assert result is not None
        assert result['strategy'] == 'balanced'
        assert result['execution_mode'] == 'patient'
        assert len(result['sets']) == 1
        assert result['sets'][0]['set_slug'] == 'test_set'


class TestGetDatabaseStats:
    """Tests for get_database_stats method."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_returns_stats(self, test_database):
        """Test that database stats are returned."""
        profit_data = [
            {"set_slug": "test", "set_name": "Test", "profit_margin": 10.0},
        ]
        set_prices = [{"slug": "test", "lowest_price": 50.0}]

        await test_database.save_market_run(profit_data, set_prices)

        stats = await test_database.get_database_stats()

        assert 'total_runs' in stats
        assert 'total_profit_records' in stats
        assert 'database_size_bytes' in stats
        assert stats['total_runs'] >= 1
        assert stats['total_profit_records'] >= 1


class TestDatabaseClose:
    """Tests for database close method."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_close_is_safe(self, test_database):
        """Test that close method doesn't raise errors."""
        await test_database.close()
        # Should be able to call close multiple times safely
        await test_database.close()
