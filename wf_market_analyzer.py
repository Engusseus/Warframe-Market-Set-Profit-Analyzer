# Warframe Market Set Profit Analyzer
# Identifies profitable item sets based on a combined score of profit and trading volume


import asyncio
import aiohttp
import pandas as pd
import numpy as np
import time
import json
import logging
import os
import glob
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from tqdm import tqdm
import matplotlib.pyplot as plt
import argparse

from config import (
    API_BASE_URL,
    REQUESTS_PER_SECOND,
    HEADERS,
    OUTPUT_FILE,
    DEBUG_MODE,
    PROFIT_WEIGHT,
    VOLUME_WEIGHT,
    PROFIT_MARGIN_WEIGHT,
    PRICE_SAMPLE_SIZE,
    USE_MEDIAN_PRICING,
    USE_STATISTICS_FOR_PRICING,
    CACHE_DIR,
    CACHE_TTL_DAYS,
    OUTPUT_FORMAT,
    DB_PATH,
)



# Configure logging
logging.basicConfig(
    level=logging.DEBUG if DEBUG_MODE else logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("wf_market_analyzer.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration is now loaded from config.py


def purge_old_cache_files() -> None:
    """Delete cache files older than the configured TTL."""
    if not os.path.isdir(CACHE_DIR):
        return
    now = datetime.now()
    for fname in os.listdir(CACHE_DIR):
        if not fname.endswith(".json"):
            continue
        parts = fname.rsplit('_', 1)
        if len(parts) < 2:
            continue
        date_str = os.path.splitext(parts[1])[0]
        try:
            file_date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            continue
        if (now - file_date).days > CACHE_TTL_DAYS:
            try:
                os.remove(os.path.join(CACHE_DIR, fname))
            except Exception as e:
                logger.warning(f"Failed to remove expired cache {fname}: {e}")


@dataclass
class SetData:
    """Data structure to hold information about a set"""
    slug: str
    name: str
    parts: Dict[str, int]  # part_slug -> quantity
    part_names: Dict[str, str]  # part_slug -> name


@dataclass
class PriceData:
    """Data structure to hold price information"""
    set_price: float
    part_prices: Dict[str, float]  # part_slug -> price
    total_part_cost: float
    profit: float
    profit_margin: float  # profit divided by total_part_cost


@dataclass
class VolumeData:
    """Data structure to hold volume information"""
    volume_48h: int
    trend: Optional[float] = None


@dataclass
class ResultData:
    """Combined results for a set"""
    set_data: SetData
    price_data: PriceData
    volume_data: VolumeData
    score: float


class WarframeMarketAPI:
    """Client for interacting with the Warframe Market API"""

    def __init__(self, cancel_token: Optional[dict] = None):
        """Initialize the API client with rate limiting"""
        self.session = None
        self.last_request_time = 0
        self.request_interval = 1.0 / REQUESTS_PER_SECOND
        self._lock = asyncio.Lock()
        self.cancel_token = cancel_token or {"stop": False}

    async def initialize(self):
        """Create the HTTP session"""
        timeout = aiohttp.ClientTimeout(total=30)  # 30-second total timeout
        self.session = aiohttp.ClientSession(headers=HEADERS, timeout=timeout)

    async def close(self):
        """Close the HTTP session"""
        if self.session:
            await self.session.close()

    async def _rate_limit(self):
        """Enforce rate limiting between requests"""
        async with self._lock:
            now = time.time()
            elapsed = now - self.last_request_time
            if elapsed < self.request_interval:
                await asyncio.sleep(self.request_interval - elapsed)
            self.last_request_time = time.time()

    async def get(self, endpoint: str, max_retries: int = 3) -> Optional[Dict]:
        """
        Make a GET request to the API with rate limiting and retry logic

        Args:
            endpoint: API endpoint (without base URL)
            max_retries: Maximum number of retry attempts

        Returns:
            Response data or None if the request failed
        """
        retries = 0
        backoff = 1  # Initial backoff in seconds

        while retries <= max_retries:
            # Fast-cancel
            if self.cancel_token.get("stop"):
                raise asyncio.CancelledError()
            await self._rate_limit()
            url = f"{API_BASE_URL}{endpoint}"

            try:
                if DEBUG_MODE:
                    logger.debug(f"Making request to: {url}")
                    logger.debug(f"Request headers: {self.session.headers}")

                async with self.session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data
                    else:
                        error_text = await response.text()
                        logger.error(f"Error {response.status} from {url}: {error_text}")

                        # Handle specific error codes
                        if response.status == 429:  # Rate limited
                            wait_time = backoff * 30  # Increased backoff
                            logger.warning(f"Rate limited! Waiting {wait_time} seconds")
                            await asyncio.sleep(wait_time)
                            backoff *= 2  # Exponential backoff
                        elif response.status >= 500:  # Server error
                            wait_time = backoff
                            logger.warning(f"Server error! Retrying in {wait_time} seconds")
                            await asyncio.sleep(wait_time)
                            backoff *= 2  # Exponential backoff
                        else:  # Client error
                            logger.error(f"Client error: {response.status} - {error_text}")
                            return None  # Don't retry client errors

                        retries += 1

            except Exception as e:
                logger.error(f"Exception while requesting {url}: {str(e)}")
                await asyncio.sleep(backoff)
                backoff *= 2  # Exponential backoff
                retries += 1

        logger.error(f"Max retries ({max_retries}) exceeded for {endpoint}")
        return None


class SetProfitAnalyzer:
    """Main class for analyzing set profits"""

    def __init__(
        self,
        analyze_trends: bool = False,
        trend_days: int = 30,
        cancel_token: Optional[dict] = None,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ):
        """Initialize the analyzer

        Args:
            analyze_trends: Whether to calculate volume trends
            trend_days: Number of days to use for trend calculations
        """
        # Ensure cache directory exists before any file operations
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
        except Exception:
            # Fall back silently; caching will be disabled if directory cannot be created
            pass
        purge_old_cache_files()
        self.cancel_token = cancel_token or {"stop": False}
        self.api = WarframeMarketAPI(cancel_token=self.cancel_token)
        self.sets = {}  # slug -> SetData
        self.results = []  # List of ResultData
        self.analyze_trends = analyze_trends
        self.trend_days = trend_days
        self.on_progress = on_progress

    def generate_scatter_plot(self) -> None:
        """Create a scatter plot of profit vs volume and save it as an image"""
        if not self.results:
            return

        output_base = os.path.splitext(OUTPUT_FILE)[0]
        plot_file = f"{output_base}_profit_vs_volume.png"

        profits = [r.price_data.profit for r in self.results]
        volumes = [r.volume_data.volume_48h for r in self.results]

        plt.figure()
        plt.scatter(volumes, profits)
        plt.xlabel("Volume (48h)")
        plt.ylabel("Profit")
        plt.title("Profit vs. Volume")
        plt.grid(True)
        plt.savefig(plot_file)
        plt.close()
        logger.info(f"Scatter plot saved to {plot_file}")

    async def initialize(self):
        """Initialize the API client"""
        await self.api.initialize()

    async def close(self):
        """Clean up resources"""
        await self.api.close()

    def _get_cache_path(self, prefix: str, slug: str, date_str: Optional[str] = None) -> str:
        """Return a cache file path for a given slug and date"""
        if date_str is None:
            date_str = time.strftime("%Y-%m-%d")
        filename = f"{prefix}_{slug}_{date_str}.json"
        return os.path.join(CACHE_DIR, filename)

    def _load_cache(self, prefix: str, slug: str) -> Optional[dict]:
        """Load cached data if available and not expired"""
        pattern = os.path.join(CACHE_DIR, f"{prefix}_{slug}_*.json")
        newest = None
        newest_date = None
        for path in glob.glob(pattern):
            date_part = os.path.splitext(path)[0].split('_')[-1]
            try:
                file_date = datetime.strptime(date_part, "%Y-%m-%d")
            except ValueError:
                continue
            if (datetime.now() - file_date).days <= CACHE_TTL_DAYS:
                if newest_date is None or file_date > newest_date:
                    newest = path
                    newest_date = file_date
        if newest:
            try:
                with open(newest, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load cache {newest}: {e}")
        return None

    def _save_cache(self, prefix: str, slug: str, data: dict) -> None:
        """Save data to cache"""
        path = self._get_cache_path(prefix, slug)
        # Ensure cache directory exists
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
        except Exception:
            pass
        try:
            with open(path, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            logger.warning(f"Failed to save cache {path}: {e}")

    async def fetch_all_items(self) -> List[Dict]:
        """Fetch all tradable items from the API"""
        logger.info("Fetching all tradable items...")
        data = await self.api.get("/items")

        if not data or 'payload' not in data:
            logger.error("Failed to fetch items")
            return []

        return data['payload']['items']

    async def extract_set_from_item_info(self, set_slug: str, item: Dict) -> Optional[SetData]:
        """Build SetData from item details."""
        if not item or 'items_in_set' not in item:
            logger.error(f"Missing items_in_set for set {set_slug}")
            return None
        set_items = item['items_in_set']
        set_name = item.get('en', {}).get('item_name', set_slug)
        parts: Dict[str, int] = {}
        part_names: Dict[str, str] = {}
        for it in set_items:
            if it.get('url_name') == set_slug:
                continue
            quantity = it.get('quantity_for_set', 1)
            part_name = it.get('en', {}).get('item_name', it.get('url_name'))
            parts[it.get('url_name')] = quantity
            part_names[it.get('url_name')] = part_name
        return SetData(slug=set_slug, name=set_name, parts=parts, part_names=part_names)

    async def fetch_orders(self, item_slug: str) -> List[Dict]:
        """
        Fetch orders for a specific item

        Args:
            item_slug: Slug identifier for the item

        Returns:
            List of orders for the item
        """
        logger.info(f"Fetching orders for: {item_slug}")

        # Avoid creating many small files: do not cache orders to disk

        data = await self.api.get(f"/items/{item_slug}/orders")

        if not data or 'payload' not in data or 'orders' not in data['payload']:
            logger.error(f"Failed to fetch orders for {item_slug}")
            return []

        # Filter to only include orders from online players
        online_statuses = ['ingame', 'online']
        orders = [
            order for order in data['payload']['orders']
            if order['user']['status'] in online_statuses
        ]

        if DEBUG_MODE:
            logger.debug(f"Found {len(orders)} orders from online players for {item_slug}")

        return orders

    async def fetch_statistics(self, item_slug: str) -> Dict:
        """Fetch statistics for a specific item (smaller payload than orders)."""
        logger.info(f"Fetching statistics for: {item_slug}")
        # Avoid creating many small files: do not cache statistics to disk
        data = await self.api.get(f"/items/{item_slug}/statistics")
        if not data or 'payload' not in data or 'statistics_closed' not in data['payload']:
            logger.error(f"Failed to fetch statistics for {item_slug}")
            return {}
        return data['payload']['statistics_closed']

    def calculate_average_price(self, orders: List[Dict], order_type: str, count: int = PRICE_SAMPLE_SIZE) -> Optional[float]:
        """
        Calculate the average price from the lowest/highest N prices

        Args:
            orders: List of orders
            order_type: 'sell' or 'buy'
            count: Number of orders to average

        Returns:
            Average price or None if not enough orders
        """
        filtered_orders = [o for o in orders if o['order_type'] == order_type]

        if len(filtered_orders) < count:
            logger.warning(f"Not enough {order_type} orders (found {len(filtered_orders)}, need {count})")
            if not filtered_orders:
                return None
            count = len(filtered_orders)  # Adjust count if we have fewer orders

        # For sell orders, we want the lowest prices (ascending)
        # For buy orders, we want the highest prices (descending)
        sorted_orders = sorted(
            filtered_orders,
            key=lambda o: o['platinum'],
            reverse=(order_type == 'buy')
        )

        # Take the average of the top N prices
        prices = [o['platinum'] for o in sorted_orders[:count]]

        # Log the prices we're using
        if DEBUG_MODE:
            logger.debug(f"Using {order_type} prices: {prices}")

        return sum(prices) / len(prices)

    def calculate_median_price(self, orders: List[Dict], order_type: str, count: int = PRICE_SAMPLE_SIZE) -> Optional[float]:
        """Calculate the median price from the lowest/highest N prices."""
        filtered_orders = [o for o in orders if o['order_type'] == order_type]

        if len(filtered_orders) < count:
            logger.warning(
                f"Not enough {order_type} orders (found {len(filtered_orders)}, need {count})"
            )
            if not filtered_orders:
                return None
            count = len(filtered_orders)

        sorted_orders = sorted(
            filtered_orders,
            key=lambda o: o['platinum'],
            reverse=(order_type == 'buy'),
        )

        prices = [o['platinum'] for o in sorted_orders[:count]]

        if DEBUG_MODE:
            logger.debug(f"Using {order_type} prices for median: {prices}")

        return float(np.median(prices))

    async def get_price_from_orders(self, item_slug: str) -> Optional[float]:
        """Get the price of an item from its orders."""
        orders = await self.fetch_orders(item_slug)
        if not orders:
            return None

        price_func = self.calculate_median_price if USE_MEDIAN_PRICING else self.calculate_average_price
        price = price_func(orders, 'sell', count=PRICE_SAMPLE_SIZE)
        return price

    async def calculate_set_profit(self, set_data: SetData) -> Optional[PriceData]:
        """
        Calculate profit for a set by fetching prices from orders.
        """
        logger.info(f"Calculating profit for set: {set_data.name}")

        set_price = await self.get_price_from_orders(set_data.slug)
        if set_price is None:
            logger.warning(f"Could not calculate sell price for set {set_data.slug}")
            return None

        # Calculate part costs
        part_prices = {}
        total_part_cost = 0
        missing_parts = []

        async def price_part(part_slug: str, quantity: int):
            nonlocal missing_parts
            p = await self.get_price_from_orders(part_slug)
            return (part_slug, p)

        results = []
        for slug, qty in set_data.parts.items():
            result = await price_part(slug, qty)
            results.append(result)
        for part_slug, p in results:
            qty = set_data.parts[part_slug]
            if p is None:
                logger.warning(f"Could not calculate price for part {part_slug}")
                missing_parts.append(part_slug)
                continue
            part_prices[part_slug] = p
            total_part_cost += p * qty

        if missing_parts:
            logger.warning(f"Skipping set {set_data.name} due to missing prices for parts: {missing_parts}")
            return None

        profit = set_price - total_part_cost
        profit_margin = 0 if total_part_cost == 0 else profit / total_part_cost

        return PriceData(
            set_price=set_price,
            part_prices=part_prices,
            total_part_cost=total_part_cost,
            profit=profit,
            profit_margin=profit_margin
        )

    async def fetch_volume_data(self, set_slug: str) -> VolumeData:
        """
        Fetch 48-hour volume data for a set, using a 1-hour cache.
        """
        logger.info(f"Fetching volume data for set: {set_slug}")

        # Check cache first
        try:
            os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            # Ensure table exists
            cur.execute("CREATE TABLE IF NOT EXISTS volume_cache (item_slug TEXT PRIMARY KEY, volume_48h INTEGER, last_updated TEXT)")
            cur.execute("SELECT volume_48h, last_updated FROM volume_cache WHERE item_slug = ?", (set_slug,))
            cached_result = cur.fetchone()
            conn.close()

            if cached_result:
                volume_48h, last_updated_str = cached_result
                last_updated = datetime.fromisoformat(last_updated_str)
                if (datetime.utcnow() - last_updated).total_seconds() < 3600:  # 1 hour
                    logger.info(f"Using cached volume for {set_slug}")
                    return VolumeData(volume_48h=volume_48h)
        except Exception as e:
            logger.error(f"Failed to read from volume cache: {e}")

        # If not in cache or expired, fetch from API
        logger.info(f"Fetching fresh volume data for {set_slug}")
        data = await self.api.get(f"/items/{set_slug}/statistics")

        volume_48h = 0
        latest_timestamp = None

        if data and 'payload' in data and 'statistics_closed' in data['payload'] and '48hours' in data['payload']['statistics_closed']:
            stats_48h = data['payload']['statistics_closed']['48hours']
            for stat in stats_48h:
                volume_48h += stat.get('volume', 0)
            if stats_48h:
                # Get the timestamp of the last entry in the 48h statistics
                latest_timestamp = stats_48h[-1].get('datetime')

        # Update cache
        if latest_timestamp:
            try:
                conn = sqlite3.connect(DB_PATH)
                cur = conn.cursor()
                cur.execute(
                    "INSERT OR REPLACE INTO volume_cache (item_slug, volume_48h, last_updated) VALUES (?, ?, ?)",
                    (set_slug, volume_48h, latest_timestamp)
                )
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"Failed to write to volume cache: {e}")

        if DEBUG_MODE:
            logger.debug(f"48-hour volume for {set_slug}: {volume_48h}")

        return VolumeData(volume_48h=volume_48h)

    async def fetch_historical_statistics(self, set_slug: str, days: int = 30) -> Dict:
        """Fetch and aggregate historical statistics for a set"""
        logger.info(f"Fetching {days}-day statistics for set: {set_slug}")

        cache = self._load_cache(f"history_{days}", set_slug)
        if cache is not None:
            return cache

        data = await self.api.get(f"/items/{set_slug}/statistics")

        history = []
        trend = None

        if data and 'payload' in data and 'statistics_closed' in data['payload']:
            stats = data['payload']['statistics_closed'].get('90days', [])
            stats = stats[-days:]
            volumes = []
            for stat in stats:
                volume = stat.get('volume', 0)
                volumes.append(volume)
                history.append({'datetime': stat.get('datetime'), 'volume': volume})

            if volumes:
                half = len(volumes) // 2
                if half > 0:
                    first = sum(volumes[:half]) / half
                    second = sum(volumes[half:]) / (len(volumes) - half)
                    if first > 0:
                        trend = (second - first) / first

        result = {'history': history, 'trend': trend}
        self._save_cache(f"history_{days}", set_slug, result)
        return result

    def normalize_data(self, results: List[ResultData]) -> List[ResultData]:
        """
        Normalize profit and volume data to a 0-1 scale

        Args:
            results: List of ResultData objects

        Returns:
            Updated ResultData objects with normalized scores
        """
        logger.info("Normalizing data and calculating scores...")

        if not results:
            return results

        # Extract profit, volume and profit margin values
        profits = [r.price_data.profit for r in results]
        volumes = [r.volume_data.volume_48h for r in results]
        margins = [r.price_data.profit_margin for r in results]

        # Calculate min/max for normalization
        min_profit = min(profits)
        max_profit = max(profits)
        profit_range = max_profit - min_profit

        min_volume = min(volumes)
        max_volume = max(volumes)
        volume_range = max_volume - min_volume

        min_margin = min(margins)
        max_margin = max(margins)
        margin_range = max_margin - min_margin

        # Normalize and calculate scores
        for result in results:
            # Avoid division by zero
            norm_profit = 0 if profit_range == 0 else (result.price_data.profit - min_profit) / profit_range
            norm_volume = 0 if volume_range == 0 else (result.volume_data.volume_48h - min_volume) / volume_range
            norm_margin = 0 if margin_range == 0 else (result.price_data.profit_margin - min_margin) / margin_range

            # Calculate weighted score
            result.score = (
                norm_profit * PROFIT_WEIGHT
                + norm_volume * VOLUME_WEIGHT
                + norm_margin * PROFIT_MARGIN_WEIGHT
            )

            if DEBUG_MODE:
                logger.debug(f"Set: {result.set_data.name}, Profit: {result.price_data.profit}, "
                             f"Volume: {result.volume_data.volume_48h}, Profit Margin: {result.price_data.profit_margin:.2f}, Score: {result.score:.4f}")

        return results

    async def process_set(self, set_item: Dict) -> Optional[ResultData]:
        """Process a single set and return its analysis result"""
        set_slug = set_item['url_name']

        # Get set parts from the item endpoint
        item_info = await self.api.get(f"/items/{set_slug}")
        if not item_info or 'payload' not in item_info or 'item' not in item_info['payload']:
            logger.error(f"Could not fetch item info for {set_slug}")
            return None

        set_data = await self.extract_set_from_item_info(set_slug, item_info['payload']['item'])
        if not set_data:
            return None

        # Enforce minimum number of online sell orders for the set
        set_orders = await self.fetch_orders(set_slug)
        online_sell_orders = [o for o in set_orders if o['order_type'] == 'sell']
        if len(online_sell_orders) < PRICE_SAMPLE_SIZE:
            logger.info(f"Skipping {set_slug}: only {len(online_sell_orders)} online sell orders (< {PRICE_SAMPLE_SIZE})")
            return None

        # Calculate profit
        price_data = await self.calculate_set_profit(set_data)
        if not price_data:
            return None

        # Fetch volume data
        volume_data = await self.fetch_volume_data(set_slug)

        if self.analyze_trends:
            history = await self.fetch_historical_statistics(set_slug, self.trend_days)
            volume_data.trend = history.get('trend')

        return ResultData(
            set_data=set_data,
            price_data=price_data,
            volume_data=volume_data,
            score=0  # Will be calculated after normalization
        )

    async def analyze_all_sets(self):
        """Main function to analyze all sets and calculate profits"""
        logger.info("Starting set profit analysis...")

        # Fetch all items
        items = await self.fetch_all_items()

        # Filter to only include prime sets (url_name ends with '_prime_set')
        set_items = [item for item in items if item.get('url_name', '').endswith('_prime_set')]
        logger.info(f"Found {len(set_items)} sets to analyze")

        tasks = [asyncio.create_task(self.process_set(item)) for item in set_items]

        results = []
        total = len(tasks)
        processed = 0
        if self.on_progress:
            try:
                self.on_progress(processed, total)
            except Exception:
                pass
        try:
            for future in tqdm(asyncio.as_completed(tasks), total=total, desc="Analyzing sets"):
                if self.cancel_token.get("stop"):
                    logger.info("Cancellation requested. Stopping analysis loop.")
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    break
                result = await future
                if result:
                    results.append(result)
                processed += 1
                if self.on_progress:
                    try:
                        self.on_progress(processed, total)
                    except Exception:
                        pass
        except asyncio.CancelledError:
            logger.warning("Analysis was cancelled.")
            for task in tasks:
                if not task.done():
                    task.cancel()

        # Normalize data and calculate scores
        results = self.normalize_data(results)

        # Sort by score (descending)
        results.sort(key=lambda r: r.score, reverse=True)

        self.results = results
        logger.info(f"Analysis complete. Found {len(results)} profitable sets.")

    def save_results(self):
        """Save results to CSV or XLSX file based on configuration"""
        # Persist results to SQLite for cumulative analytics instead of CSV/JSON outputs
        try:
            os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            # Main table for per-run results
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS set_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_ts TEXT NOT NULL,
                    platform TEXT,
                    set_slug TEXT,
                    set_name TEXT,
                    profit REAL,
                    profit_margin REAL,
                    set_price REAL,
                    part_cost_total REAL,
                    volume_48h INTEGER,
                    score REAL
                )
                """
            )
            # New table for volume cache
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS volume_cache (
                    item_slug TEXT PRIMARY KEY,
                    volume_48h INTEGER,
                    last_updated TEXT
                )
                """
            )
            # Optional volume table for future expansions (single DB, no files)
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS volume_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_ts TEXT NOT NULL,
                    set_slug TEXT,
                    volume_48h INTEGER
                )
                """
            )

            run_ts = datetime.utcnow().isoformat()
            platform = HEADERS.get("Platform", "pc")
            rows = []
            for result in self.results:
                rows.append(
                    (
                        run_ts,
                        platform,
                        result.set_data.slug,
                        result.set_data.name,
                        float(round(result.price_data.profit, 6)),
                        float(round(result.price_data.profit_margin, 6)),
                        float(round(result.price_data.set_price, 6)),
                        float(round(result.price_data.total_part_cost, 6)),
                        int(result.volume_data.volume_48h),
                        float(round(result.score, 6)),
                    )
                )

            cur.executemany(
                """
                INSERT INTO set_results (
                    run_ts, platform, set_slug, set_name, profit, profit_margin,
                    set_price, part_cost_total, volume_48h, score
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            # Also persist volumes to the table (one row per set)
            vol_rows = [(run_ts, r.set_data.slug, int(r.volume_data.volume_48h)) for r in self.results]
            cur.executemany(
                "INSERT INTO volume_snapshots (run_ts, set_slug, volume_48h) VALUES (?, ?, ?)",
                vol_rows,
            )
            conn.commit()
            conn.close()
            logger.info(f"Persisted {len(rows)} rows to {DB_PATH}")
        except Exception as e:
            logger.error(f"Failed to persist results to SQLite: {e}")

    def save_to_csv(self):
        """Backward compatibility wrapper."""
        self.save_results()


def run_analysis_ui(
    platform='pc',
    profit_weight=1.0,
    volume_weight=1.2,
    profit_margin_weight=0.0,
    price_sample_size=2,
    use_median_pricing=False,
    use_statistics_for_pricing=False,
    analyze_trends=False,
    trend_days=30,
    debug=False,
    persist=True,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    cancel_token: Optional[dict] = None,
):
    """
    Run the analyzer and return a DataFrame and raw results for UI use.
    Does not save files or plots.
    """
    import asyncio
    global HEADERS, PROFIT_WEIGHT, VOLUME_WEIGHT, PROFIT_MARGIN_WEIGHT, PRICE_SAMPLE_SIZE, USE_MEDIAN_PRICING, USE_STATISTICS_FOR_PRICING, DEBUG_MODE
    HEADERS["Platform"] = platform
    PROFIT_WEIGHT = profit_weight
    VOLUME_WEIGHT = volume_weight
    PROFIT_MARGIN_WEIGHT = profit_margin_weight
    PRICE_SAMPLE_SIZE = price_sample_size
    USE_MEDIAN_PRICING = use_median_pricing
    USE_STATISTICS_FOR_PRICING = use_statistics_for_pricing
    DEBUG_MODE = debug

    if DEBUG_MODE:
        logger.setLevel(logging.DEBUG)

    analyzer = SetProfitAnalyzer(
        analyze_trends=analyze_trends,
        trend_days=trend_days,
        cancel_token=cancel_token or {"stop": False},
        on_progress=progress_callback,
    )

    async def _run():
        await analyzer.initialize()
        try:
            await analyzer.analyze_all_sets()
            # Only persist if not cancelled
            if persist and not analyzer.cancel_token.get("stop"):
                analyzer.save_results()
        finally:
            await analyzer.close()
        # Prepare DataFrame
        csv_data = []
        for result in analyzer.results:
            part_prices_str = "; ".join([
                f"{result.set_data.part_names.get(slug, slug)} (x{qty}): {result.price_data.part_prices.get(slug, 0):.1f}"
                for slug, qty in result.set_data.parts.items()
            ])
            row = {
                'Set Name': result.set_data.name,
                'Profit': round(result.price_data.profit, 1),
                'Profit Margin': round(result.price_data.profit_margin, 2),
                'Set Selling Price': round(result.price_data.set_price, 1),
                'Part Costs Total': round(result.price_data.total_part_cost, 1),
                'Volume (48h)': result.volume_data.volume_48h,
                'Score': round(result.score, 4),
                'Part Prices': part_prices_str
            }
            csv_data.append(row)
        df = pd.DataFrame(csv_data)
        return df, analyzer.results

    return asyncio.run(_run())


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(description="Warframe Market Set Profit Analyzer")
    parser.add_argument("--platform", default=HEADERS.get("Platform", "pc"), help="Platform to query (pc, ps4, xbox, switch)")
    parser.add_argument("--output-file", default=OUTPUT_FILE, help="Path to the output CSV file")
    parser.add_argument("--output-format", default=OUTPUT_FORMAT, choices=['csv', 'xlsx'], help="Output file format")
    parser.add_argument("--profit-weight", type=float, default=PROFIT_WEIGHT, help="Weight for profit in score calculation")
    parser.add_argument("--volume-weight", type=float, default=VOLUME_WEIGHT, help="Weight for 48h volume in score calculation")
    parser.add_argument("--profit-margin-weight", type=float, default=PROFIT_MARGIN_WEIGHT, help="Weight for profit margin in score calculation")
    parser.add_argument("--price-sample-size", type=int, default=PRICE_SAMPLE_SIZE, help="Number of orders used when averaging prices")
    parser.add_argument("--use-median-pricing", action="store_true", default=USE_MEDIAN_PRICING, help="Use median price calculations")
    parser.add_argument("--trend-days", type=int, help="Calculate volume trend over the last N days")
    parser.add_argument("--debug", action="store_true", default=DEBUG_MODE, help="Enable debug logging")
    return parser.parse_args()


async def main(args: argparse.Namespace) -> None:
    """Main entry point"""
    global OUTPUT_FILE, OUTPUT_FORMAT, PROFIT_WEIGHT, VOLUME_WEIGHT, PROFIT_MARGIN_WEIGHT, PRICE_SAMPLE_SIZE, DEBUG_MODE, USE_MEDIAN_PRICING

    # Apply command-line overrides
    HEADERS["Platform"] = args.platform
    OUTPUT_FILE = args.output_file
    OUTPUT_FORMAT = args.output_format
    PROFIT_WEIGHT = args.profit_weight
    VOLUME_WEIGHT = args.volume_weight
    PROFIT_MARGIN_WEIGHT = args.profit_margin_weight
    PRICE_SAMPLE_SIZE = args.price_sample_size
    USE_MEDIAN_PRICING = args.use_median_pricing
    DEBUG_MODE = args.debug

    if DEBUG_MODE:
        logger.setLevel(logging.DEBUG)

    analyzer = SetProfitAnalyzer(
        analyze_trends=args.trend_days is not None,
        trend_days=args.trend_days or 30,
    )

    try:
        await analyzer.initialize()
        await analyzer.analyze_all_sets()
        analyzer.save_results()
    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}", exc_info=True)
    finally:
        await analyzer.close()


def run_analysis_in_process(queue, **kwargs):
    """
    Wrapper to run the analysis in a separate process and put the result in a queue.
    """
    try:
        df, results = run_analysis_ui(**kwargs)
        queue.put((df, results))
    except Exception as e:
        queue.put(e)


if __name__ == "__main__":
    print("=== Warframe Market Set Profit Analyzer ===")
    args = parse_arguments()
    print(f"Output will be saved to: {args.output_file}")
    print("Starting analysis...")

    asyncio.run(main(args))

    print("Analysis complete!")
