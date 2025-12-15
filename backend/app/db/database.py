"""Async database module for persistent storage of market run data.

Enhanced version of database.py with async support using aiosqlite.
"""
import asyncio
import json
import os
import sqlite3
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiosqlite

from ..config import get_settings


class AsyncMarketDatabase:
    """Async SQLite database handler for market analysis data.

    Thread-safe async SQLite database handler with transaction support.
    """

    # Database schema version for future migrations
    SCHEMA_VERSION = 1

    def __init__(self, db_path: Optional[str] = None):
        """Initialize database connection and ensure table exists."""
        if db_path is None:
            settings = get_settings()
            db_path = settings.database_path

        self.db_path = os.path.abspath(db_path)
        self._lock = asyncio.Lock()

        # Validate database path
        if not self.db_path.endswith('.sqlite'):
            raise ValueError("Database path must end with .sqlite extension")

        # Ensure cache directory exists
        db_dir = os.path.dirname(self.db_path)
        os.makedirs(db_dir, exist_ok=True)

        # Initialize database synchronously on first use
        self._initialized = False

    async def _ensure_initialized(self) -> None:
        """Ensure database is initialized."""
        if not self._initialized:
            await self._create_tables()
            await self._configure_database()
            self._initialized = True

    async def _create_tables(self) -> None:
        """Create database tables if they don't exist."""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as conn:
                # Create market_runs table
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS market_runs (
                        run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp INTEGER NOT NULL,
                        date_string TEXT NOT NULL
                    )
                ''')

                # Create set_profits table
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS set_profits (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        run_id INTEGER NOT NULL,
                        set_slug TEXT NOT NULL,
                        set_name TEXT NOT NULL,
                        profit_margin REAL NOT NULL,
                        lowest_price REAL NOT NULL,
                        FOREIGN KEY (run_id) REFERENCES market_runs (run_id),
                        UNIQUE(run_id, set_slug)
                    )
                ''')

                # Create indexes for better performance
                await conn.execute(
                    'CREATE INDEX IF NOT EXISTS idx_set_profits_run_id ON set_profits(run_id)'
                )
                await conn.execute(
                    'CREATE INDEX IF NOT EXISTS idx_set_profits_set_slug ON set_profits(set_slug)'
                )
                await conn.execute(
                    'CREATE INDEX IF NOT EXISTS idx_market_runs_timestamp ON market_runs(timestamp)'
                )

                # Create metadata table for schema versioning
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS metadata (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    )
                ''')

                # Set schema version
                await conn.execute(
                    'INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)',
                    ('schema_version', str(self.SCHEMA_VERSION))
                )

                await conn.commit()

    async def _configure_database(self) -> None:
        """Configure database settings for optimal performance and safety."""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as conn:
                # Enable foreign key constraints
                await conn.execute('PRAGMA foreign_keys = ON')
                # Set WAL mode for better concurrency
                await conn.execute('PRAGMA journal_mode = WAL')
                # Set synchronous mode for better performance while maintaining safety
                await conn.execute('PRAGMA synchronous = NORMAL')
                await conn.commit()

    def _validate_market_run_data(
        self,
        profit_data: List[Dict[str, Any]],
        set_prices: List[Dict[str, Any]]
    ) -> None:
        """Validate input data for market run."""
        if not profit_data:
            raise ValueError("profit_data cannot be empty")
        if not set_prices:
            raise ValueError("set_prices cannot be empty")

        # Validate profit_data structure
        required_profit_fields = ['set_slug', 'set_name', 'profit_margin']
        for i, item in enumerate(profit_data):
            if not isinstance(item, dict):
                raise ValueError(f"profit_data[{i}] must be a dictionary")
            for field in required_profit_fields:
                if field not in item:
                    raise ValueError(f"profit_data[{i}] missing required field: {field}")

        # Validate set_prices structure
        required_price_fields = ['slug', 'lowest_price']
        for i, item in enumerate(set_prices):
            if not isinstance(item, dict):
                raise ValueError(f"set_prices[{i}] must be a dictionary")
            for field in required_price_fields:
                if field not in item:
                    raise ValueError(f"set_prices[{i}] missing required field: {field}")

    async def save_market_run(
        self,
        profit_data: List[Dict[str, Any]],
        set_prices: List[Dict[str, Any]]
    ) -> int:
        """Save complete market run data using a transaction.

        Args:
            profit_data: List of profit analysis results
            set_prices: List of set pricing data

        Returns:
            int: The run_id of the saved run

        Raises:
            ValueError: If input data is invalid
            Exception: If transaction fails
        """
        await self._ensure_initialized()

        # Validate input data
        self._validate_market_run_data(profit_data, set_prices)

        timestamp = int(time.time())
        date_string = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

        # Create lookup for set prices
        price_lookup = {item['slug']: item['lowest_price'] for item in set_prices}

        async with self._lock:
            async with aiosqlite.connect(self.db_path) as conn:
                try:
                    # Insert market run record
                    cursor = await conn.execute(
                        'INSERT INTO market_runs (timestamp, date_string) VALUES (?, ?)',
                        (timestamp, date_string)
                    )
                    run_id = cursor.lastrowid

                    # Batch insert set profit records for better performance
                    profit_records = []
                    for profit_item in profit_data:
                        set_slug = profit_item['set_slug']
                        lowest_price = price_lookup.get(set_slug, 0)

                        profit_records.append((
                            run_id,
                            set_slug,
                            profit_item['set_name'],
                            profit_item['profit_margin'],
                            lowest_price
                        ))

                    await conn.executemany('''
                        INSERT INTO set_profits
                        (run_id, set_slug, set_name, profit_margin, lowest_price)
                        VALUES (?, ?, ?, ?, ?)
                    ''', profit_records)

                    # Commit the transaction
                    await conn.commit()
                    return run_id

                except Exception as e:
                    # Transaction will be rolled back automatically
                    await conn.rollback()
                    raise Exception(f"Failed to save market run: {e}")

    async def get_run_count(self) -> int:
        """Get total number of market runs in database."""
        await self._ensure_initialized()

        async with self._lock:
            async with aiosqlite.connect(self.db_path) as conn:
                cursor = await conn.execute('SELECT COUNT(*) FROM market_runs')
                row = await cursor.fetchone()
                return row[0] if row else 0

    async def get_latest_run_id(self) -> Optional[int]:
        """Get the ID of the most recent market run."""
        await self._ensure_initialized()

        async with self._lock:
            async with aiosqlite.connect(self.db_path) as conn:
                cursor = await conn.execute(
                    'SELECT run_id FROM market_runs ORDER BY timestamp DESC LIMIT 1'
                )
                result = await cursor.fetchone()
                return result[0] if result else None

    async def get_run_by_id(self, run_id: int) -> Optional[Dict[str, Any]]:
        """Get complete data for a specific run.

        Args:
            run_id: The run ID to fetch

        Returns:
            Run data dictionary or None if not found
        """
        await self._ensure_initialized()

        async with self._lock:
            async with aiosqlite.connect(self.db_path) as conn:
                # Get run info
                cursor = await conn.execute(
                    'SELECT run_id, timestamp, date_string FROM market_runs WHERE run_id = ?',
                    (run_id,)
                )
                run_row = await cursor.fetchone()
                if not run_row:
                    return None

                # Get set profits
                cursor = await conn.execute('''
                    SELECT set_slug, set_name, profit_margin, lowest_price
                    FROM set_profits WHERE run_id = ?
                    ORDER BY profit_margin DESC
                ''', (run_id,))
                profit_rows = await cursor.fetchall()

                set_profits = [
                    {
                        'set_slug': row[0],
                        'set_name': row[1],
                        'profit_margin': row[2],
                        'lowest_price': row[3]
                    }
                    for row in profit_rows
                ]

                return {
                    'run_id': run_row[0],
                    'timestamp': run_row[1],
                    'date_string': run_row[2],
                    'set_profits': set_profits
                }

    async def get_run_summary(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get summary of recent market runs."""
        await self._ensure_initialized()

        if limit <= 0:
            raise ValueError("limit must be positive")

        async with self._lock:
            async with aiosqlite.connect(self.db_path) as conn:
                cursor = await conn.execute('''
                    SELECT
                        mr.run_id,
                        mr.date_string,
                        COUNT(sp.id) as set_count,
                        AVG(sp.profit_margin) as avg_profit,
                        MAX(sp.profit_margin) as max_profit
                    FROM market_runs mr
                    LEFT JOIN set_profits sp ON mr.run_id = sp.run_id
                    GROUP BY mr.run_id, mr.date_string
                    ORDER BY mr.timestamp DESC
                    LIMIT ?
                ''', (limit,))

                columns = ['run_id', 'date_string', 'set_count', 'avg_profit', 'max_profit']
                rows = await cursor.fetchall()
                return [dict(zip(columns, row)) for row in rows]

    async def get_set_price_history(
        self,
        set_slug: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get price history for a specific set."""
        await self._ensure_initialized()

        if not set_slug or not set_slug.strip():
            raise ValueError("set_slug cannot be empty")
        if limit <= 0:
            raise ValueError("limit must be positive")

        async with self._lock:
            async with aiosqlite.connect(self.db_path) as conn:
                cursor = await conn.execute('''
                    SELECT
                        mr.date_string,
                        mr.timestamp,
                        sp.profit_margin,
                        sp.lowest_price
                    FROM set_profits sp
                    JOIN market_runs mr ON sp.run_id = mr.run_id
                    WHERE sp.set_slug = ?
                    ORDER BY mr.timestamp DESC
                    LIMIT ?
                ''', (set_slug, limit))

                columns = ['date_string', 'timestamp', 'profit_margin', 'lowest_price']
                rows = await cursor.fetchall()
                return [dict(zip(columns, row)) for row in rows]

    async def get_profit_trends(
        self,
        set_slug: str,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get profit trends for a set over time.

        Args:
            set_slug: Set identifier
            days: Number of days to look back

        Returns:
            List of trend data points
        """
        await self._ensure_initialized()

        cutoff_time = int(time.time()) - (days * 24 * 3600)

        async with self._lock:
            async with aiosqlite.connect(self.db_path) as conn:
                cursor = await conn.execute('''
                    SELECT
                        mr.date_string,
                        mr.timestamp,
                        sp.profit_margin,
                        sp.lowest_price
                    FROM set_profits sp
                    JOIN market_runs mr ON sp.run_id = mr.run_id
                    WHERE sp.set_slug = ? AND mr.timestamp >= ?
                    ORDER BY mr.timestamp ASC
                ''', (set_slug, cutoff_time))

                columns = ['date_string', 'timestamp', 'profit_margin', 'lowest_price']
                rows = await cursor.fetchall()
                return [dict(zip(columns, row)) for row in rows]

    async def get_all_sets(self) -> List[Dict[str, Any]]:
        """Get all unique sets from database.

        Returns:
            List of set info dictionaries
        """
        await self._ensure_initialized()

        async with self._lock:
            async with aiosqlite.connect(self.db_path) as conn:
                cursor = await conn.execute('''
                    SELECT DISTINCT set_slug, set_name
                    FROM set_profits
                    ORDER BY set_name
                ''')

                rows = await cursor.fetchall()
                return [{'slug': row[0], 'name': row[1]} for row in rows]

    async def export_to_json(self) -> Dict[str, Any]:
        """Export entire database to a structured JSON format for analysis."""
        await self._ensure_initialized()

        async with self._lock:
            async with aiosqlite.connect(self.db_path) as conn:
                # Get all market runs
                cursor = await conn.execute(
                    'SELECT run_id, timestamp, date_string FROM market_runs ORDER BY timestamp'
                )
                runs = [
                    dict(zip(['run_id', 'timestamp', 'date_string'], row))
                    for row in await cursor.fetchall()
                ]

                # Build export data
                export_data = {
                    'metadata': {
                        'export_timestamp': int(time.time()),
                        'export_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'total_runs': len(runs),
                        'database_path': self.db_path
                    },
                    'market_runs': []
                }

                for run in runs:
                    run_id = run['run_id']

                    # Get all set profits for this run
                    cursor = await conn.execute('''
                        SELECT set_slug, set_name, profit_margin, lowest_price
                        FROM set_profits
                        WHERE run_id = ?
                        ORDER BY set_name
                    ''', (run_id,))

                    set_profits = [
                        {
                            'set_slug': row[0],
                            'set_name': row[1],
                            'profit_margin': row[2],
                            'lowest_price': row[3]
                        }
                        for row in await cursor.fetchall()
                    ]

                    run_data = {
                        'run_info': run,
                        'set_profits': set_profits,
                        'summary': {
                            'total_sets': len(set_profits),
                            'average_profit': sum(s['profit_margin'] for s in set_profits) / len(set_profits) if set_profits else 0,
                            'max_profit': max((s['profit_margin'] for s in set_profits), default=0),
                            'min_profit': min((s['profit_margin'] for s in set_profits), default=0),
                            'profitable_sets': len([s for s in set_profits if s['profit_margin'] > 0])
                        }
                    }

                    export_data['market_runs'].append(run_data)

                return export_data

    async def save_json_export(
        self,
        output_path: str = "cache/market_data_export.json"
    ) -> str:
        """Save JSON export to file.

        Args:
            output_path: Path to save the JSON file

        Returns:
            str: Path to the saved file
        """
        export_data = await self.export_to_json()

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        return output_path

    async def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        await self._ensure_initialized()

        async with self._lock:
            async with aiosqlite.connect(self.db_path) as conn:
                # Get run count
                cursor = await conn.execute('SELECT COUNT(*) FROM market_runs')
                run_count = (await cursor.fetchone())[0]

                # Get total set profits recorded
                cursor = await conn.execute('SELECT COUNT(*) FROM set_profits')
                profit_count = (await cursor.fetchone())[0]

                # Get date range
                cursor = await conn.execute(
                    'SELECT MIN(timestamp), MAX(timestamp) FROM market_runs'
                )
                time_range = await cursor.fetchone()

                stats = {
                    'total_runs': run_count,
                    'total_profit_records': profit_count,
                    'database_size_bytes': os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
                }

                if time_range[0] and time_range[1]:
                    stats['first_run'] = datetime.fromtimestamp(time_range[0]).strftime('%Y-%m-%d %H:%M:%S')
                    stats['last_run'] = datetime.fromtimestamp(time_range[1]).strftime('%Y-%m-%d %H:%M:%S')
                    stats['time_span_days'] = (time_range[1] - time_range[0]) / (24 * 3600)

                return stats

    async def vacuum_database(self) -> None:
        """Optimize database by running VACUUM operation."""
        await self._ensure_initialized()

        async with self._lock:
            async with aiosqlite.connect(self.db_path) as conn:
                # Vacuum cannot be run inside a transaction
                await conn.execute('VACUUM')

    async def close(self) -> None:
        """Close database connection and cleanup resources."""
        # Currently no persistent connections to close
        pass


# Singleton instance
_database_instance: Optional[AsyncMarketDatabase] = None


async def get_database_instance() -> AsyncMarketDatabase:
    """Get a singleton database instance."""
    global _database_instance
    if _database_instance is None:
        _database_instance = AsyncMarketDatabase()
    return _database_instance
