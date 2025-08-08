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
    CONCURRENCY_LIMIT,
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
    trend: Optional[float] = None  # volume trend ratio over window
    price_trend_pct: Optional[float] = None  # price % change over window
    price_slope_per_day: Optional[float] = None  # regression slope per day


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
        """Initialize the API client with concurrency and rate limiting"""
        self.session = None
        self.last_request_time = 0
        self.request_interval = 1.0 / REQUESTS_PER_SECOND
        self._lock = asyncio.Lock()
        # Token bucket state
        self._semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
        self._rate_lock = asyncio.Lock()
        self._request_timestamps: List[float] = []
        self._rps_budget = max(1, REQUESTS_PER_SECOND)
        self._stats = {"total_requests": 0, "errors": 0, "429": 0, "started": time.time()}
        self.cancel_token = cancel_token or {"stop": False}

    async def initialize(self):
        """Create the HTTP session"""
        connector = aiohttp.TCPConnector(limit=CONCURRENCY_LIMIT, ttl_dns_cache=300)
        self.session = aiohttp.ClientSession(headers=HEADERS, connector=connector)

    async def close(self):
        """Close the HTTP session"""
        if self.session:
            await self.session.close()

    async def _rate_limit(self):
        """Token-bucket style limiter to keep average RPS under budget."""
        async with self._rate_lock:
            now = time.time()
            # Drop timestamps older than 1 second
            self._request_timestamps = [t for t in self._request_timestamps if now - t < 1.0]
            if len(self._request_timestamps) >= self._rps_budget:
                sleep_for = 1.0 - (now - self._request_timestamps[0])
                if sleep_for > 0:
                    await asyncio.sleep(sleep_for)
            # Record token consumption
            self._request_timestamps.append(time.time())

    async def get(self, endpoint: str, max_retries: int = 3) -> Optional[Dict]:
        """
        Make a GET request to the API with rate limiting and retry logic.
        Returns parsed JSON on 200, None otherwise.
        """
        retries = 0
        backoff = 1.0
        while retries <= max_retries:
            # Cooperative cancel
            if self.cancel_token.get("stop"):
                raise asyncio.CancelledError()
            await self._rate_limit()
            url = f"{API_BASE_URL}{endpoint}"
            try:
                if DEBUG_MODE:
                    logger.debug(f"GET {url}")
                async with self._semaphore:
                    await self._rate_limit()
                    async with self.session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            self._stats["total_requests"] += 1
                            return data
                        else:
                            error_text = await response.text()
                            logger.error(f"HTTP {response.status} for {url}: {error_text}")
                            self._stats["errors"] += 1
                            if response.status == 429:
                                self._stats["429"] += 1
                                wait_time = backoff * 3.0
                                logger.warning(f"Rate limited; sleeping {wait_time:.1f}s")
                                await asyncio.sleep(wait_time)
                                backoff = min(backoff * 2.0, 30.0)
                            elif response.status >= 500:
                                wait_time = backoff
                                logger.warning(f"Server error {response.status}; retry in {wait_time:.1f}s")
                                await asyncio.sleep(wait_time)
                                backoff = min(backoff * 2.0, 30.0)
                            else:
                                return None
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.exception(f"Request error for {url}: {e}")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, 30.0)
            retries += 1
        logger.error(f"Max retries ({max_retries}) exceeded for {endpoint}")
        return None
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
        self._failures = 0

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

    async def extract_set_from_include(self, set_slug: str, include: Dict) -> Optional[SetData]:
        """Build SetData from include.item.items_in_set provided by orders?include=item."""
        item = include.get('item') if include else None
        if not item or 'items_in_set' not in item:
            logger.error(f"Missing include.item for set {set_slug}")
            return None
        set_items = item['items_in_set']
        set_name = None
        parts: Dict[str, int] = {}
        part_names: Dict[str, str] = {}
        for it in set_items:
            if it.get('url_name') == set_slug:
                set_name = it.get('en', {}).get('item_name', set_slug)
        if not set_name:
            set_name = set_slug
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

    @staticmethod
    def _quantile(values: List[float], q: float) -> Optional[float]:
        if not values:
            return None
        try:
            return float(np.quantile(np.array(values, dtype=float), q))
        except Exception:
            return None

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

    async def calculate_set_profit(self, set_data: SetData, conservative_pricing: bool = False, min_samples_quantile: int = 8) -> Optional[PriceData]:
        """
        Calculate profit for a set

        Args:
            set_data: SetData object with set and part information

        Returns:
            PriceData object or None if prices could not be calculated
        """
        logger.info(f"Calculating profit for set: {set_data.name}")

        # Always use statistics for pricing (faster)
        stats = await self.fetch_statistics(set_data.slug)
        # Use last 48h closed stats prices
        series_48h = stats.get('48hours', []) if stats else []
        prices = [s.get('median') or s.get('avg_price') for s in series_48h if s.get('median') or s.get('avg_price')]
        sample_count = len(prices)
        if sample_count >= min_samples_quantile:
            if conservative_pricing:
                set_price = self._quantile(prices, 0.25)
            else:
                set_price = float(np.median(prices))
        elif sample_count >= 3:
            set_price = float(np.median(prices))
        else:
            set_price = None
        if set_price is None:
            logger.error(f"Could not calculate sell price for set {set_data.slug}")
            return None

        # Calculate part costs
        part_prices = {}
        total_part_cost = 0
        missing_parts = []

        async def price_part(part_slug: str, quantity: int):
            nonlocal missing_parts
            try:
                stats = await self.fetch_statistics(part_slug)
                series_48h = stats.get('48hours', []) if stats else []
                prices = [s.get('median') or s.get('avg_price') for s in series_48h if s.get('median') or s.get('avg_price')]
                # Enforce minimum sample size threshold for robust pricing
                if len(prices) >= min_samples_quantile:
                    if conservative_pricing:
                        p = self._quantile(prices, 0.75)
                    else:
                        p = float(np.median(prices))
                elif len(prices) >= 3:
                    p = float(np.median(prices))
                else:
                    p = None
                return (part_slug, p)
            except Exception:
                return (part_slug, None)

        tasks = [asyncio.create_task(price_part(slug, qty)) for slug, qty in set_data.parts.items()]
        results = await asyncio.gather(*tasks)
        for part_slug, p in results:
            qty = set_data.parts[part_slug]
            if p is None:
                logger.warning(f"Could not calculate price for part {part_slug}")
                missing_parts.append(part_slug)
                continue
            part_prices[part_slug] = p
            total_part_cost += p * qty

        # Skip sets with missing part prices
        if missing_parts:
            logger.warning(f"Skipping set {set_data.name} due to missing prices for parts: {missing_parts}")
            return None

        # Calculate profit
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
        Fetch 48-hour volume data for a set

        Args:
            set_slug: Slug identifier for the set

        Returns:
            VolumeData object with volume information
        """
        logger.info(f"Fetching volume data for set: {set_slug}")

        # No on-disk caching to avoid many small files

        # Use the statistics endpoint to get volume data
        data = await self.api.get(f"/items/{set_slug}/statistics")

        volume_48h = 0

        if data and 'payload' in data and 'statistics_closed' in data['payload'] and '48hours' in data['payload']['statistics_closed']:
            # Extract volume from 48-hour statistics
            for stat in data['payload']['statistics_closed']['48hours']:
                volume_48h += stat.get('volume', 0)

        if DEBUG_MODE:
            logger.debug(f"48-hour volume for {set_slug}: {volume_48h}")

        return VolumeData(volume_48h=volume_48h)

    async def fetch_historical_statistics(self, set_slug: str, days: int = 30) -> Dict:
        """Fetch and aggregate historical statistics for a set (volume and price)."""
        logger.info(f"Fetching {days}-day statistics for set: {set_slug}")

        cache = self._load_cache(f"history_{days}", set_slug)
        if cache is not None:
            return cache

        data = await self.api.get(f"/items/{set_slug}/statistics")

        history = []
        volume_trend = None
        price_trend_pct = None
        price_slope = None

        if data and 'payload' in data and 'statistics_closed' in data['payload']:
            stats = data['payload']['statistics_closed'].get('90days', [])
            stats = stats[-days:]
            volumes = []
            medians = []
            x_idx = list(range(len(stats)))
            for stat in stats:
                volume = stat.get('volume', 0)
                volumes.append(volume)
                median_price = stat.get('median') or stat.get('avg_price')
                medians.append(median_price if median_price is not None else None)
                history.append({'datetime': stat.get('datetime'), 'volume': volume, 'median': median_price})

            if volumes:
                half = len(volumes) // 2
                if half > 0:
                    first = sum(volumes[:half]) / half
                    second = sum(volumes[half:]) / (len(volumes) - half)
                    if first > 0:
                        volume_trend = (second - first) / first
            # Price trend % and slope
            clean_pairs = [(i, m) for i, m in zip(x_idx, medians) if m is not None]
            if len(clean_pairs) >= 5:
                x = np.array([i for i, _ in clean_pairs], dtype=float)
                y = np.array([m for _, m in clean_pairs], dtype=float)
                # Percent change
                first_val, last_val = y[0], y[-1]
                if first_val > 0:
                    price_trend_pct = float(((last_val - first_val) / first_val) * 100.0)
                # Simple linear regression slope (per index ~ day)
                x_mean, y_mean = float(np.mean(x)), float(np.mean(y))
                denom = float(np.sum((x - x_mean) ** 2))
                if denom > 0:
                    slope = float(np.sum((x - x_mean) * (y - y_mean)) / denom)
                    price_slope = slope

        result = {
            'history': history,
            'volume_trend': volume_trend,
            'price_trend_pct': price_trend_pct,
            'price_slope_per_day': price_slope,
        }
        self._save_cache(f"history_{days}", set_slug, result)
        return result

    def normalize_data(self, results: List[ResultData], robust: bool = False) -> List[ResultData]:
        """Normalize features and compute composite score.
    
        - Filters invalid or non-positive rows first.
        - Two modes:
          * robust=True: rank-based normalization with tie-aware average ranks.
          * robust=False: min-max normalization.
        """
        if not results:
            return results
    
        # Filter invalid rows first (prevent skew and NaN issues)
        filtered: List[ResultData] = []
        for r in results:
            try:
                if not np.isfinite(r.price_data.profit) or not np.isfinite(r.price_data.profit_margin):
                    continue
                if r.price_data.profit <= 0 or r.volume_data.volume_48h <= 0:
                    continue
                filtered.append(r)
            except Exception:
                continue
    
        if not filtered:
            return filtered
    
        profits = np.array([r.price_data.profit for r in filtered], dtype=float)
        volumes = np.array([r.volume_data.volume_48h for r in filtered], dtype=float)
        margins = np.array([r.price_data.profit_margin for r in filtered], dtype=float)
    
        N = len(filtered)
    
        if robust:
            # Tie-aware average ranks on ascending arrays (lower value -> lower rank)
            def avg_ranks(arr: np.ndarray) -> dict:
                order = np.argsort(arr)
                sorted_vals = arr[order]
                ranks = {}
                i = 0
                n = len(sorted_vals)
                while i < n:
                    j = i + 1
                    while j < n and sorted_vals[j] == sorted_vals[i]:
                        j += 1
                    avg = (i + (j - 1)) / 2.0
                    ranks[sorted_vals[i]] = avg
                    i = j
                return ranks
    
            r_profit = avg_ranks(profits)
            r_volume = avg_ranks(volumes)
            r_margin = avg_ranks(margins)
    
            for r in filtered:
                rp = r_profit[r.price_data.profit]
                rv = r_volume[r.volume_data.volume_48h]
                rm = r_margin[r.price_data.profit_margin]
                norm_profit = (N - 1 - rp) / (N - 1) if N > 1 else 0.0
                norm_volume = (N - 1 - rv) / (N - 1) if N > 1 else 0.0
                norm_margin = (N - 1 - rm) / (N - 1) if N > 1 else 0.0
                r.score = (
                    norm_profit * PROFIT_WEIGHT
                    + norm_volume * VOLUME_WEIGHT
                    + norm_margin * PROFIT_MARGIN_WEIGHT
                )
        else:
            # Min-max normalization
            p_min, p_max = float(np.min(profits)), float(np.max(profits))
            v_min, v_max = float(np.min(volumes)), float(np.max(volumes))
            m_min, m_max = float(np.min(margins)), float(np.max(margins))
            p_rng = max(p_max - p_min, 1e-9)
            v_rng = max(v_max - v_min, 1e-9)
            m_rng = max(m_max - m_min, 1e-9)
            for r in filtered:
                norm_profit = (r.price_data.profit - p_min) / p_rng
                norm_volume = (r.volume_data.volume_48h - v_min) / v_rng
                norm_margin = (r.price_data.profit_margin - m_min) / m_rng
                r.score = (
                    norm_profit * PROFIT_WEIGHT
                    + norm_volume * VOLUME_WEIGHT
                    + norm_margin * PROFIT_MARGIN_WEIGHT
                )
    
        # Replace original list in-place order preserved
        return filtered

    async def process_set(self, set_item: Dict, conservative_pricing: bool = False, min_samples_quantile: int = 8) -> Optional[ResultData]:
        """Process a single set and return its analysis result"""
        set_slug = set_item['url_name']

        # Prefer pulling include.item along with orders to avoid separate item fetch
        include_resp = await self.api.get(f"/items/{set_slug}/orders?include=item")
        if not include_resp or 'payload' not in include_resp:
            self._failures += 1
            return None
        include = include_resp.get('include', {})
        set_data = await self.extract_set_from_include(set_slug, include)
        if not set_data:
            return None

        # Enforce minimum number of online sell orders for the set
        online_statuses = ['ingame', 'online']
        orders = include_resp.get('payload', {}).get('orders', [])
        online_sell = [o for o in orders if o.get('order_type') == 'sell' and o.get('user', {}).get('status') in online_statuses]
        if len(online_sell) < PRICE_SAMPLE_SIZE:
            logger.info(f"Skipping {set_slug}: only {len(online_sell)} online sell orders (< {PRICE_SAMPLE_SIZE})")
            return None

        # Calculate profit
        price_data = await self.calculate_set_profit(set_data, conservative_pricing=conservative_pricing, min_samples_quantile=min_samples_quantile)
        if not price_data:
            self._failures += 1
            return None

        # Fetch volume data
        volume_data = await self.fetch_volume_data(set_slug)

        if self.analyze_trends:
            history = await self.fetch_historical_statistics(set_slug, self.trend_days)
            volume_data.trend = history.get('volume_trend')
            volume_data.price_trend_pct = history.get('price_trend_pct')
            volume_data.price_slope_per_day = history.get('price_slope_per_day')

        return ResultData(
            set_data=set_data,
            price_data=price_data,
            volume_data=volume_data,
            score=0  # Will be calculated after normalization
        )

    async def analyze_all_sets(
        self,
        conservative_pricing: bool = False,
        robust_score: bool = False,
        min_samples_quantile: int = 8,
        min_profit_threshold: float = 0.0,
        min_margin_threshold: float = 0.0,
        min_volume_threshold: float = 0.0,
    ):
        """Main function to analyze all sets and calculate profits"""
        logger.info("Starting set profit analysis...")

        # Fetch all items
        items = await self.fetch_all_items()

        # Filter to only include sets (url_name ends with '_set')
        set_items = [item for item in items if item.get('url_name', '').endswith('_set')]
        logger.info(f"Found {len(set_items)} sets to analyze")

        tasks = [asyncio.create_task(self.process_set(item, conservative_pricing=conservative_pricing, min_samples_quantile=min_samples_quantile)) for item in set_items]

        results = []
        total = len(tasks)
        processed = 0
        if self.on_progress:
            try:
                self.on_progress(processed, total)
            except Exception:
                pass
        for future in tqdm(asyncio.as_completed(tasks), total=total, desc="Analyzing sets"):
            if self.cancel_token.get("stop"):
                logger.info("Cancellation requested. Stopping analysis loop.")
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

        # Threshold filtering BEFORE normalization to prevent skew
        prefiltered: List[ResultData] = []
        for r in results:
            try:
                if r.price_data.profit <= float(min_profit_threshold):
                    continue
                if r.price_data.profit_margin <= float(min_margin_threshold):
                    continue
                if float(r.volume_data.volume_48h) < float(min_volume_threshold):
                    continue
                prefiltered.append(r)
            except Exception:
                continue

        # Normalize data and calculate scores
        results = self.normalize_data(prefiltered, robust=robust_score)

        # Sort by score (descending)
        results.sort(key=lambda r: r.score, reverse=True)

        self.results = results
        logger.info(f"Analysis complete. Found {len(results)} sets. Failures: {self._failures}")

    def save_results(self, platform: Optional[str] = None, config_json: Optional[str] = None):
        """Persist results to SQLite.
        - If platform/config_json provided: use normalized schema (runs, set_metrics) with WAL.
        - Else: legacy schema (set_results, volume_snapshots) for CLI compatibility.
        """
        try:
            import sqlite3
            os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            # Pragmas for durability/perf
            cur.execute("PRAGMA journal_mode=WAL;")
            cur.execute("PRAGMA synchronous=NORMAL;")
            cur.execute("PRAGMA foreign_keys=ON;")

            if platform is not None and config_json is not None:
                # New schema
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS runs (
                        run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ts_utc TEXT NOT NULL,
                        platform TEXT,
                        config_json TEXT
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS set_metrics (
                        run_id INTEGER NOT NULL,
                        set_slug TEXT,
                        set_name TEXT,
                        profit REAL,
                        profit_margin REAL,
                        set_price REAL,
                        part_cost_total REAL,
                        volume_48h INTEGER,
                        eta_hours REAL,
                        profit_per_day REAL,
                        score REAL,
                        PRIMARY KEY (run_id, set_slug),
                        FOREIGN KEY (run_id) REFERENCES runs(run_id)
                    )
                    """
                )
                cur.execute("CREATE INDEX IF NOT EXISTS idx_set_metrics_run ON set_metrics(run_id);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_set_metrics_slug ON set_metrics(set_slug);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_runs_ts ON runs(ts_utc);")

                cur.execute("BEGIN;")
                ts = datetime.utcnow().isoformat()
                cur.execute("INSERT INTO runs (ts_utc, platform, config_json) VALUES (?, ?, ?)", (ts, platform, config_json))
                run_id = cur.lastrowid
                rows = []
                for r in self.results:
                    lambda_per_hour = max(0.0, float(r.volume_data.volume_48h) / 48.0)
                    eta_hours = float('inf') if lambda_per_hour <= 0 else max(0.5, 1.0 / lambda_per_hour)
                    profit_per_day = float(r.price_data.profit) * (24.0 / (eta_hours if np.isfinite(eta_hours) else 24.0))
                    rows.append(
                        (
                            run_id,
                            r.set_data.slug,
                            r.set_data.name,
                            float(round(r.price_data.profit, 6)),
                            float(round(r.price_data.profit_margin, 6)),
                            float(round(r.price_data.set_price, 6)),
                            float(round(r.price_data.total_part_cost, 6)),
                            int(r.volume_data.volume_48h),
                            float(round(eta_hours if np.isfinite(eta_hours) else 999999.0, 6)),
                            float(round(profit_per_day, 6)),
                            float(round(r.score, 6)),
                        )
                    )
                cur.executemany(
                    """
                    INSERT OR REPLACE INTO set_metrics (
                        run_id, set_slug, set_name, profit, profit_margin, set_price, part_cost_total,
                        volume_48h, eta_hours, profit_per_day, score
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )
                conn.commit()
                conn.close()
                logger.info(f"Persisted run {run_id} with {len(rows)} rows to {DB_PATH}")
                return

            # Legacy schema path
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
            legacy_platform = HEADERS.get("Platform", "pc")
            rows = []
            for result in self.results:
                rows.append(
                    (
                        run_ts,
                        legacy_platform,
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
    conservative_pricing: bool = False,
    robust_score: bool = False,
    analyze_trends=False,
    trend_days=30,
    trade_tax_percent: float = 0.0,
    min_profit_threshold: float = 0.0,
    min_margin_threshold: float = 0.0,
    min_volume_threshold: float = 0.0,
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
            await analyzer.analyze_all_sets(
                conservative_pricing=conservative_pricing,
                robust_score=robust_score,
                min_samples_quantile=max(3, price_sample_size * 4),
                min_profit_threshold=float(min_profit_threshold),
                min_margin_threshold=float(min_margin_threshold),
                min_volume_threshold=float(min_volume_threshold),
            )
            # Only persist if not cancelled
            if persist and not analyzer.cancel_token.get("stop"):
                cfg = {
                    "platform": platform,
                    "profit_weight": profit_weight,
                    "volume_weight": volume_weight,
                    "profit_margin_weight": profit_margin_weight,
                    "price_sample_size": price_sample_size,
                    "use_statistics_for_pricing": use_statistics_for_pricing,
                    "conservative_pricing": conservative_pricing,
                    "robust_score": robust_score,
                    "analyze_trends": analyze_trends,
                    "trend_days": trend_days,
                    "trade_tax_percent": trade_tax_percent,
                }
                analyzer.save_results(platform=platform, config_json=json.dumps(cfg))
        finally:
            await analyzer.close()
        # Prepare DataFrame
        csv_data = []
        for result in analyzer.results:
            # Apply trade tax and compute ETA/profit per day
            net_profit = float(result.price_data.profit) * (1.0 - float(trade_tax_percent) / 100.0)
            lambda_per_hour = max(0.0, float(result.volume_data.volume_48h) / 48.0)
            eta_hours = float('inf') if lambda_per_hour <= 0 else max(0.5, 1.0 / lambda_per_hour)
            profit_per_day = net_profit * (24.0 / (eta_hours if np.isfinite(eta_hours) else 24.0))
            part_prices_str = "; ".join([
                f"{result.set_data.part_names.get(slug, slug)} (x{qty}): {result.price_data.part_prices.get(slug, 0):.1f}"
                for slug, qty in result.set_data.parts.items()
            ])
            row = {
                'Set Slug': result.set_data.slug,
                'Set Name': result.set_data.name,
                'Profit': round(net_profit, 1),
                'Profit Margin': round(result.price_data.profit_margin, 2),
                'Set Selling Price': round(result.price_data.set_price, 1),
                'Part Costs Total': round(result.price_data.total_part_cost, 1),
                'Volume (48h)': result.volume_data.volume_48h,
                'ETA (hours)': None if not np.isfinite(eta_hours) else round(eta_hours, 2),
                'Profit/Day': round(profit_per_day, 1),
                'Score': round(result.score, 4),
                'Part Prices': part_prices_str,
                'Market': f"https://warframe.market/items/{result.set_data.slug}",
            }
            if analyze_trends and result.volume_data.price_trend_pct is not None:
                row[f'Trend % ({trend_days}d)'] = round(float(result.volume_data.price_trend_pct), 2)
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
        # Persist using new schema with minimal config
        cfg = {
            "platform": HEADERS.get("Platform", "pc"),
            "profit_weight": PROFIT_WEIGHT,
            "volume_weight": VOLUME_WEIGHT,
            "profit_margin_weight": PROFIT_MARGIN_WEIGHT,
            "price_sample_size": PRICE_SAMPLE_SIZE,
        }
        analyzer.save_results(platform=HEADERS.get("Platform", "pc"), config_json=json.dumps(cfg))
    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}", exc_info=True)
    finally:
        await analyzer.close()


def cli_entry() -> None:
    """Console script entry point."""
    args = parse_arguments()
    asyncio.run(main(args))


if __name__ == "__main__":
    print("=== Warframe Market Set Profit Analyzer ===")
    args = parse_arguments()
    print(f"Output will be saved to: {args.output_file}")
    print("Starting analysis...")

    asyncio.run(main(args))

    print("Analysis complete!")