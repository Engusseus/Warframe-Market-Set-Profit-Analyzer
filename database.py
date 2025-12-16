"""Database module for persistent storage of market run data."""
import os
import sqlite3
import json
import time
import threading
import queue
import contextlib
from datetime import datetime
from typing import List, Dict, Any, Optional


class SQLiteConnectionPool:
    """Simple connection pool for SQLite connections."""

    def __init__(self, db_path: str, max_connections: int = 5):
        self.db_path = db_path
        self.max_connections = max_connections
        self._pool = queue.Queue(maxsize=max_connections)

    def get(self) -> sqlite3.Connection:
        """Get a connection from the pool or create a new one."""
        try:
            return self._pool.get_nowait()
        except queue.Empty:
            # Create a new connection if pool is empty
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._configure_connection(conn)
            return conn

    def put(self, conn: sqlite3.Connection):
        """Return a connection to the pool."""
        try:
            self._pool.put_nowait(conn)
        except queue.Full:
            # If pool is full, close the connection
            conn.close()

    def close_all(self):
        """Close all connections in the pool."""
        while True:
            try:
                conn = self._pool.get_nowait()
                conn.close()
            except queue.Empty:
                break

    def _configure_connection(self, conn: sqlite3.Connection):
        """Configure a new connection with necessary PRAGMAs."""
        # Enable foreign key constraints
        conn.execute('PRAGMA foreign_keys = ON')
        # Set synchronous mode for better performance while maintaining safety
        conn.execute('PRAGMA synchronous = NORMAL')


class MarketDatabase:
    """SQLite database handler for market analysis data.
    
    Thread-safe SQLite database handler with transaction support.
    """
    
    # Database schema version for future migrations
    SCHEMA_VERSION = 1
    
    def __init__(self, db_path: str = "cache/market_runs.sqlite"):
        """Initialize database connection and ensure table exists."""
        self.db_path = os.path.abspath(db_path)  # Use absolute path
        self._lock = threading.RLock()  # Thread safety
        
        # Validate database path
        if not self.db_path.endswith('.sqlite'):
            raise ValueError("Database path must end with .sqlite extension")
        
        # Ensure cache directory exists
        db_dir = os.path.dirname(self.db_path)
        os.makedirs(db_dir, exist_ok=True)
        
        # Initialize connection pool
        self.pool = SQLiteConnectionPool(self.db_path)

        # Initialize database with proper settings
        self._create_tables()
        self._configure_database()
    
    @contextlib.contextmanager
    def managed_connection(self):
        """Context manager for obtaining a pooled connection with transaction support."""
        conn = self.pool.get()
        try:
            with conn:
                yield conn
        finally:
            self.pool.put(conn)

    def _create_tables(self):
        """Create database tables if they don't exist."""
        with self._lock:
            with self.managed_connection() as conn:
                cursor = conn.cursor()
                
                # Create market_runs table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS market_runs (
                        run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp INTEGER NOT NULL,
                        date_string TEXT NOT NULL
                    )
                ''')
                
                # Create set_profits table
                cursor.execute('''
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
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_set_profits_run_id ON set_profits(run_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_set_profits_set_slug ON set_profits(set_slug)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_market_runs_timestamp ON market_runs(timestamp)')
                
                # Create metadata table for schema versioning
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS metadata (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    )
                ''')
                
                # Set schema version
                cursor.execute('INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)',
                             ('schema_version', str(self.SCHEMA_VERSION)))
                
                # managed_connection handles commit automatically via 'with conn:'
    
    def _configure_database(self):
        """Configure database settings for optimal performance and safety."""
        with self._lock:
            with self.managed_connection() as conn:
                # Set WAL mode for better concurrency (persistent setting)
                conn.execute('PRAGMA journal_mode = WAL')
                # Other per-connection settings are handled by the pool
    
    def _validate_market_run_data(self, profit_data: List[Dict[str, Any]], set_prices: List[Dict[str, Any]]) -> None:
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
    
    def save_market_run(self, profit_data: List[Dict[str, Any]], set_prices: List[Dict[str, Any]]) -> int:
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
        # Validate input data
        self._validate_market_run_data(profit_data, set_prices)
        
        timestamp = int(time.time())
        date_string = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        
        # Create lookup for set prices
        price_lookup = {item['slug']: item['lowest_price'] for item in set_prices}
        
        with self._lock:
            # Use pooled connection
            # managed_connection handles transaction start and commit/rollback
            try:
                with self.managed_connection() as conn:
                    cursor = conn.cursor()
                    
                    # Insert market run record
                    cursor.execute(
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
                    
                    cursor.executemany('''
                        INSERT INTO set_profits 
                        (run_id, set_slug, set_name, profit_margin, lowest_price)
                        VALUES (?, ?, ?, ?, ?)
                    ''', profit_records)
                    
                    return run_id
            except Exception as e:
                # The managed_connection context manager handles rollback
                # We re-raise to notify caller
                raise Exception(f"Failed to save market run: {e}")
    
    def get_run_count(self) -> int:
        """Get total number of market runs in database."""
        with self._lock:
            with self.managed_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM market_runs')
                return cursor.fetchone()[0]
    
    def get_latest_run_id(self) -> Optional[int]:
        """Get the ID of the most recent market run."""
        with self._lock:
            with self.managed_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT run_id FROM market_runs ORDER BY timestamp DESC LIMIT 1')
                result = cursor.fetchone()
                return result[0] if result else None
    
    def get_run_summary(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get summary of recent market runs."""
        if limit <= 0:
            raise ValueError("limit must be positive")
            
        with self._lock:
            with self.managed_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
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
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def get_set_price_history(self, set_slug: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get price history for a specific set."""
        if not set_slug or not set_slug.strip():
            raise ValueError("set_slug cannot be empty")
        if limit <= 0:
            raise ValueError("limit must be positive")
            
        with self._lock:
            with self.managed_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
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
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def export_to_json(self) -> Dict[str, Any]:
        """Export entire database to a structured JSON format for analysis.
        
        Returns:
            Dict containing all market run data in a structured format
        """
        with self._lock:
            with self.managed_connection() as conn:
                cursor = conn.cursor()
            
                # Get all market runs
                cursor.execute('SELECT run_id, timestamp, date_string FROM market_runs ORDER BY timestamp')
                runs = [dict(zip(['run_id', 'timestamp', 'date_string'], row)) for row in cursor.fetchall()]
                
                # Get all set profit data grouped by run
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
                    cursor.execute('''
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
                        for row in cursor.fetchall()
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
    
    def save_json_export(self, output_path: str = "cache/market_data_export.json") -> str:
        """Save JSON export to file.
        
        Args:
            output_path: Path to save the JSON file
            
        Returns:
            str: Path to the saved file
        """
        export_data = self.export_to_json()
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        return output_path
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        with self._lock:
            with self.managed_connection() as conn:
                cursor = conn.cursor()
            
                # Get run count
                cursor.execute('SELECT COUNT(*) FROM market_runs')
                run_count = cursor.fetchone()[0]

                # Get total set profits recorded
                cursor.execute('SELECT COUNT(*) FROM set_profits')
                profit_count = cursor.fetchone()[0]

                # Get date range
                cursor.execute('SELECT MIN(timestamp), MAX(timestamp) FROM market_runs')
                time_range = cursor.fetchone()

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
    
    def close(self) -> None:
        """Close database connection and cleanup resources."""
        self.pool.close_all()
    
    def vacuum_database(self) -> None:
        """Optimize database by running VACUUM operation.
        
        This reclaims unused space and optimizes the database file.
        Should be run periodically on databases with many deletions.
        """
        with self._lock:
            # VACUUM cannot run inside a transaction
            # managed_connection uses 'with conn' which starts a transaction
            # So we need to get a connection manually and handle it
            conn = self.pool.get()
            try:
                old_isolation = conn.isolation_level
                conn.isolation_level = None  # Enable autocommit mode
                try:
                    conn.execute('VACUUM')
                finally:
                    conn.isolation_level = old_isolation
            finally:
                self.pool.put(conn)


def get_database_instance() -> MarketDatabase:
    """Get a singleton database instance."""
    if not hasattr(get_database_instance, '_instance'):
        get_database_instance._instance = MarketDatabase()
    return get_database_instance._instance
