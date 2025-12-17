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
    SCHEMA_VERSION = 2

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

                # Create scored_set_data table for full analysis storage
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS scored_set_data (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        run_id INTEGER NOT NULL,
                        set_slug TEXT NOT NULL,
                        set_name TEXT NOT NULL,
                        set_price REAL NOT NULL,
                        part_cost REAL NOT NULL,
                        profit_margin REAL NOT NULL,
                        profit_percentage REAL NOT NULL,
                        volume INTEGER NOT NULL,
                        normalized_profit REAL NOT NULL,
                        normalized_volume REAL NOT NULL,
                        profit_score REAL NOT NULL,
                        volume_score REAL NOT NULL,
                        total_score REAL NOT NULL,
                        part_details TEXT NOT NULL,
                        trend_slope REAL DEFAULT 0,
                        trend_multiplier REAL DEFAULT 1.0,
                        trend_direction TEXT DEFAULT 'stable',
                        volatility REAL DEFAULT 0,
                        volatility_penalty REAL DEFAULT 1.0,
                        risk_level TEXT DEFAULT 'Medium',
                        composite_score REAL DEFAULT 0,
                        profit_contribution REAL DEFAULT 0,
                        volume_contribution REAL DEFAULT 0,
                        trend_contribution REAL DEFAULT 1.0,
                        volatility_contribution REAL DEFAULT 1.0,
                        FOREIGN KEY (run_id) REFERENCES market_runs (run_id),
                        UNIQUE(run_id, set_slug)
                    )
                ''')

                # Create run_metadata table for weights and summary
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS run_metadata (
                        run_id INTEGER PRIMARY KEY,
                        profit_weight REAL NOT NULL,
                        volume_weight REAL NOT NULL,
                        total_sets INTEGER NOT NULL,
                        profitable_sets INTEGER NOT NULL,
                        strategy TEXT DEFAULT 'balanced',
                        FOREIGN KEY (run_id) REFERENCES market_runs (run_id)
                    )
                ''')

                # Create index for scored_set_data
                await conn.execute(
                    'CREATE INDEX IF NOT EXISTS idx_scored_set_data_run_id ON scored_set_data(run_id)'
                )

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

    async def get_price_history_batch(
        self,
        set_slugs: List[str],
        days: int = 7
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Batch fetch historical price data for multiple sets.

        This is more efficient than calling get_profit_trends() for each set
        when calculating trend/volatility metrics for all sets.

        Args:
            set_slugs: List of set identifiers to fetch
            days: Number of days to look back

        Returns:
            Dict mapping set_slug to list of {timestamp, lowest_price} entries
        """
        await self._ensure_initialized()

        if not set_slugs:
            return {}

        cutoff_time = int(time.time()) - (days * 24 * 3600)

        async with self._lock:
            async with aiosqlite.connect(self.db_path) as conn:
                # Use parameterized query for the set_slugs
                placeholders = ','.join('?' * len(set_slugs))
                query = f'''
                    SELECT
                        sp.set_slug,
                        mr.timestamp,
                        sp.lowest_price
                    FROM set_profits sp
                    JOIN market_runs mr ON sp.run_id = mr.run_id
                    WHERE sp.set_slug IN ({placeholders}) AND mr.timestamp >= ?
                    ORDER BY sp.set_slug, mr.timestamp ASC
                '''

                cursor = await conn.execute(query, (*set_slugs, cutoff_time))
                rows = await cursor.fetchall()

                # Group results by set_slug
                result: Dict[str, List[Dict[str, Any]]] = {slug: [] for slug in set_slugs}
                for row in rows:
                    set_slug, timestamp, lowest_price = row
                    if set_slug in result:
                        result[set_slug].append({
                            'timestamp': timestamp,
                            'lowest_price': lowest_price
                        })

                return result

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

    async def save_full_analysis(
        self,
        run_id: int,
        scored_data: List[Dict[str, Any]],
        profit_weight: float = 1.0,
        volume_weight: float = 1.2,
        strategy: str = 'balanced'
    ) -> None:
        """Save full scored analysis data for a run.

        Args:
            run_id: The run ID to associate data with
            scored_data: List of scored set data dictionaries
            profit_weight: Profit weight used for scoring (legacy)
            volume_weight: Volume weight used for scoring (legacy)
            strategy: Strategy type used for scoring
        """
        await self._ensure_initialized()

        if not scored_data:
            return

        profitable_count = len([s for s in scored_data if s.get('profit_margin', 0) > 0])

        async with self._lock:
            async with aiosqlite.connect(self.db_path) as conn:
                try:
                    # Save run metadata with strategy
                    await conn.execute('''
                        INSERT OR REPLACE INTO run_metadata
                        (run_id, profit_weight, volume_weight, total_sets, profitable_sets, strategy)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (run_id, profit_weight, volume_weight, len(scored_data), profitable_count, strategy))

                    # Batch insert scored set data with new fields
                    records = []
                    for item in scored_data:
                        part_details_json = json.dumps(item.get('part_details', []))
                        records.append((
                            run_id,
                            item.get('set_slug', ''),
                            item.get('set_name', ''),
                            item.get('set_price', 0),
                            item.get('part_cost', 0),
                            item.get('profit_margin', 0),
                            item.get('profit_percentage', 0),
                            item.get('volume', 0),
                            item.get('normalized_profit', 0),
                            item.get('normalized_volume', 0),
                            item.get('profit_score', 0),
                            item.get('volume_score', 0),
                            item.get('total_score', 0),
                            part_details_json,
                            item.get('trend_slope', 0),
                            item.get('trend_multiplier', 1.0),
                            item.get('trend_direction', 'stable'),
                            item.get('volatility', 0),
                            item.get('volatility_penalty', 1.0),
                            item.get('risk_level', 'Medium'),
                            item.get('composite_score', 0),
                            item.get('profit_contribution', 0),
                            item.get('volume_contribution', 0),
                            item.get('trend_contribution', 1.0),
                            item.get('volatility_contribution', 1.0)
                        ))

                    await conn.executemany('''
                        INSERT OR REPLACE INTO scored_set_data
                        (run_id, set_slug, set_name, set_price, part_cost, profit_margin,
                         profit_percentage, volume, normalized_profit, normalized_volume,
                         profit_score, volume_score, total_score, part_details,
                         trend_slope, trend_multiplier, trend_direction, volatility,
                         volatility_penalty, risk_level, composite_score,
                         profit_contribution, volume_contribution, trend_contribution,
                         volatility_contribution)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', records)

                    await conn.commit()

                except Exception as e:
                    await conn.rollback()
                    raise Exception(f"Failed to save full analysis: {e}")

    async def get_full_analysis(self, run_id: int) -> Optional[Dict[str, Any]]:
        """Get full scored analysis data for a run.

        Args:
            run_id: The run ID to fetch

        Returns:
            Dictionary with full analysis data or None if not found
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

                # Get run metadata (weights and strategy)
                cursor = await conn.execute(
                    'SELECT profit_weight, volume_weight, total_sets, profitable_sets, strategy FROM run_metadata WHERE run_id = ?',
                    (run_id,)
                )
                metadata_row = await cursor.fetchone()

                # Get scored set data with new fields
                cursor = await conn.execute('''
                    SELECT set_slug, set_name, set_price, part_cost, profit_margin,
                           profit_percentage, volume, normalized_profit, normalized_volume,
                           profit_score, volume_score, total_score, part_details,
                           trend_slope, trend_multiplier, trend_direction, volatility,
                           volatility_penalty, risk_level, composite_score,
                           profit_contribution, volume_contribution, trend_contribution,
                           volatility_contribution
                    FROM scored_set_data WHERE run_id = ?
                    ORDER BY composite_score DESC
                ''', (run_id,))
                set_rows = await cursor.fetchall()

                # If no scored data exists, return None
                if not set_rows:
                    return None

                # Build scored sets list with new fields
                scored_sets = []
                for row in set_rows:
                    part_details = json.loads(row[12]) if row[12] else []
                    scored_sets.append({
                        'set_slug': row[0],
                        'set_name': row[1],
                        'set_price': row[2],
                        'part_cost': row[3],
                        'profit_margin': row[4],
                        'profit_percentage': row[5],
                        'volume': row[6],
                        'normalized_profit': row[7],
                        'normalized_volume': row[8],
                        'profit_score': row[9],
                        'volume_score': row[10],
                        'total_score': row[11],
                        'part_details': part_details,
                        'trend_slope': row[13] if row[13] is not None else 0.0,
                        'trend_multiplier': row[14] if row[14] is not None else 1.0,
                        'trend_direction': row[15] if row[15] is not None else 'stable',
                        'volatility': row[16] if row[16] is not None else 0.0,
                        'volatility_penalty': row[17] if row[17] is not None else 1.0,
                        'risk_level': row[18] if row[18] is not None else 'Medium',
                        'composite_score': row[19] if row[19] is not None else row[11],
                        'profit_contribution': row[20] if row[20] is not None else 0.0,
                        'volume_contribution': row[21] if row[21] is not None else 0.0,
                        'trend_contribution': row[22] if row[22] is not None else 1.0,
                        'volatility_contribution': row[23] if row[23] is not None else 1.0
                    })

                # Build response
                result = {
                    'run_id': run_row[0],
                    'timestamp': run_row[1],
                    'date_string': run_row[2],
                    'sets': scored_sets,
                    'total_sets': len(scored_sets),
                    'profitable_sets': len([s for s in scored_sets if s['profit_margin'] > 0])
                }

                # Add weights and strategy if available
                if metadata_row:
                    result['weights'] = {
                        'profit_weight': metadata_row[0],
                        'volume_weight': metadata_row[1],
                        'strategy': metadata_row[4] if metadata_row[4] else 'balanced'
                    }
                    result['total_sets'] = metadata_row[2]
                    result['profitable_sets'] = metadata_row[3]
                    result['strategy'] = metadata_row[4] if metadata_row[4] else 'balanced'
                else:
                    result['weights'] = {
                        'profit_weight': 1.0,
                        'volume_weight': 1.2,
                        'strategy': 'balanced'
                    }
                    result['strategy'] = 'balanced'

                return result

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
