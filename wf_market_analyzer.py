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
    RPS_LIMIT,
    MAX_CONCURRENCY,
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
    """Client for interacting with the Warframe Market API with proper rate limiting and concurrency control"""

    def __init__(self, cancel_token: Optional[dict] = None):
        """Initialize the API client with rate limiting and concurrency control"""
        self.session = None
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
        self._rate_lock = asyncio.Lock()
        self._request_timestamps: List[float] = []
        self._rps_budget = RPS_LIMIT
        self._stats = {"total_requests": 0, "errors": 0, "429": 0, "started": time.time()}
        self.cancel_token = cancel_token or {"stop": False}

    async def initialize(self):
        """Create the HTTP session with proper connector settings"""
        connector = aiohttp.TCPConnector(limit=MAX_CONCURRENCY, ttl_dns_cache=300)
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
        Make a GET request to the API with rate limiting, concurrency control, and retry logic

        Args:
            endpoint: API endpoint (without base URL)
            max_retries: Maximum number of retry attempts

        Returns:
            Response data or None if the request failed
        """
        retries = 0
        backoff = 1  # Initial backoff in seconds

        while retries <= max_retries:
            # Fast-cancel check
            if self.cancel_token.get("stop"):
                raise asyncio.CancelledError()
            
            url = f"{API_BASE_URL}{endpoint}"

            try:
                if DEBUG_MODE:
                    logger.debug(f"Making request to: {url}")

                async with self._semaphore:
                    await self._rate_limit()
                    async with self.session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            self._stats["total_requests"] += 1
                            return data
                        else:
                            error_text = await response.text()
                            logger.error(f"Error {response.status} from {url}: {error_text}")
                            self._stats["errors"] += 1

                            # Handle specific error codes
                            if response.status == 429:  # Rate limited
                                wait_time = backoff * 3  # Longer backoff for rate limiting
                                logger.warning(f"Rate limited! Waiting {wait_time} seconds")
                                self._stats["429"] += 1
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
    """Main class for analyzing set profits with robust pricing and scoring"""

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
        """Compute quantile with proper error handling"""
        if not values:
            return None
        try:
            return float(np.quantile(np.array(values, dtype=float), q))
        except Exception:
            return None

    async def calculate_set_profit(self, set_data: SetData, conservative_pricing: bool = False, min_samples_quantile: int = 8) -> Optional[PriceData]:
        """
        Calculate profit for a set with robust pricing options

        Args:
            set_data: SetData object with set and part information
            conservative_pricing: If True, use P25 for sell price and P75 for buy prices
            min_samples_quantile: Minimum samples required for quantile-based pricing

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
        """
        Normalize profit and volume data to a 0-1 scale with robust options

        Args:
            results: List of ResultData objects
            robust: If True, use rank-based normalization instead of min-max

        Returns:
            Updated ResultData objects with normalized scores
        """
        logger.info("Normalizing data and calculating scores...")

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
            return []

        profits = [r.price_data.profit for r in filtered]
        volumes = [r.volume_data.volume_48h for r in filtered]
        margins = [r.price_data.profit_margin for r in filtered]

        if robust:
            # Rank-based normalization (descending)
            N = len(filtered)
            sp = sorted(profits)
            sv = sorted(volumes)
            sm = sorted(margins)
            r_profit = {v: i for i, v in enumerate(sp)}
            r_volume = {v: i for i, v in enumerate(sv)}
            r_margin = {v: i for i, v in enumerate(sm)}
            for r in filtered:
                rp = r_profit[r.price_data.profit]
                rv = r_volume[r.volume_data.volume_48h]
                rm = r_margin[r.price_data.profit_margin]
                norm_profit = (N - 1 - rp) / (N - 1) if N > 1 else 0
                norm_volume = (N - 1 - rv) / (N - 1) if N > 1 else 0
                norm_margin = (N - 1 - rm) / (N - 1) if N > 1 else 0
                r.score = (
                    norm_profit * PROFIT_WEIGHT
                    + norm_volume * VOLUME_WEIGHT
                    + norm_margin * PROFIT_MARGIN_WEIGHT
                )
        else:
            # Min-max normalization
            min_profit, max_profit = min(profits), max(profits)
            min_volume, max_volume = min(volumes), max(volumes)
            min_margin, max_margin = min(margins), max(margins)
            profit_range = max_profit - min_profit
            volume_range = max_volume - min_volume
            margin_range = max_margin - min_margin
            for r in filtered:
                norm_profit = 0 if profit_range == 0 else (r.price_data.profit - min_profit) / profit_range
                norm_volume = 0 if volume_range == 0 else (r.volume_data.volume_48h - min_volume) / volume_range
                norm_margin = 0 if margin_range == 0 else (r.price_data.profit_margin - min_margin) / margin_range
                r.score = (
                    norm_profit * PROFIT_WEIGHT
                    + norm_volume * VOLUME_WEIGHT
                    + norm_margin * PROFIT_MARGIN_WEIGHT
                )

        if DEBUG_MODE:
            for r in filtered:
                logger.debug(
                    f"Set: {r.set_data.name}, Profit: {r.price_data.profit}, Volume: {r.volume_data.volume_48h}, Profit Margin: {r.price_data.profit_margin:.2f}, Score: {r.score:.4f}"
                )

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
        start_time = time.time()

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
        elapsed = time.time() - start_time
        # Log basic run stats
        logger.info(
            f"Analysis complete. Found {len(results)} sets. Failures: {self._failures}. Runtime: {elapsed:.1f}s"
        )

    def save_results(self, platform: Optional[str] = None, config_json: Optional[str] = None):
        """Persist results to SQLite using normalized schema with proper PRAGMAs."""
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
                # New normalized schema
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS runs (
                        run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ts_utc TEXT NOT NULL,
                        platform TEXT NOT NULL,
                        config_json TEXT NOT NULL
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS set_metrics (
                        run_id INTEGER NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
                        set_slug TEXT NOT NULL,
                        set_name TEXT NOT NULL,
                        price_sell REAL,
                        price_cost REAL,
                        profit REAL,
                        margin REAL,
                        volume_48h REAL,
                        eta_hours REAL,
                        profit_per_day REAL,
                        score REAL,
                        trend_pct REAL,
                        conservative_pricing INTEGER NOT NULL,
                        robust_score INTEGER NOT NULL,
                        trade_tax_percent REAL NOT NULL,
                        UNIQUE(run_id, set_slug)
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
                    trend_pct = r.volume_data.price_trend_pct if r.volume_data.price_trend_pct is not None else None
                    
                    rows.append(
                        (
                            run_id,
                            r.set_data.slug,
                            r.set_data.name,
                            float(round(r.price_data.set_price, 6)),
                            float(round(r.price_data.total_part_cost, 6)),
                            float(round(r.price_data.profit, 6)),
                            float(round(r.price_data.profit_margin, 6)),
                            int(r.volume_data.volume_48h),
                            float(round(eta_hours if np.isfinite(eta_hours) else 999999.0, 6)),
                            float(round(profit_per_day, 6)),
                            float(round(r.score, 6)),
                            float(round(trend_pct, 6)) if trend_pct is not None else None,
                            1 if hasattr(self, '_conservative_pricing') and self._conservative_pricing else 0,
                            1 if hasattr(self, '_robust_score') and self._robust_score else 0,
                            float(getattr(self, '_trade_tax_percent', 0.0)),
                        )
                    )
                cur.executemany(
                    """
                    INSERT OR REPLACE INTO set_metrics (
                        run_id, set_slug, set_name, price_sell, price_cost, profit, margin,
                        volume_48h, eta_hours, profit_per_day, score, trend_pct,
                        conservative_pricing, robust_score, trade_tax_percent
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )
                conn.commit()
                conn.close()
                logger.info(f"Persisted run {run_id} with {len(rows)} rows to {DB_PATH}")
                return

            # Legacy schema path (for CLI compatibility)
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
    
    # Store settings for persistence
    analyzer._conservative_pricing = conservative_pricing
    analyzer._robust_score = robust_score
    analyzer._trade_tax_percent = trade_tax_percent

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
                    "min_profit_threshold": min_profit_threshold,
                    "min_margin_threshold": min_margin_threshold,
                    "min_volume_threshold": min_volume_threshold,
                }
                analyzer.save_results(platform=platform, config_json=json.dumps(cfg))
        finally:
            await analyzer.close()
        # Prepare DataFrame with required columns
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
                'Set Name': result.set_data.name,
                'Set Slug': result.set_data.slug,
                'Price (sell)': round(result.price_data.set_price, 1),
                'Price (cost)': round(result.price_data.total_part_cost, 1),
                'Profit': round(net_profit, 1),
                'Margin': round(result.price_data.profit_margin, 2),
                'Volume (48h)': result.volume_data.volume_48h,
                'ETA (h)': None if not np.isfinite(eta_hours) else round(eta_hours, 2),
                'Profit/day': round(profit_per_day, 1),
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


def cli_entry():
    """CLI entry point for the analyzer"""
    import argparse
    import asyncio
    import sys
    
    # Global declarations must come before any usage
    global HEADERS, PROFIT_WEIGHT, VOLUME_WEIGHT, PROFIT_MARGIN_WEIGHT, DEBUG_MODE
    
    parser = argparse.ArgumentParser(description="Warframe Market Set Profit Analyzer")
    parser.add_argument("--platform", default="pc", choices=["pc", "xbox", "ps4", "switch"], 
                       help="Platform to analyze")
    parser.add_argument("--output-file", default=OUTPUT_FILE, 
                       help="Output file name")
    parser.add_argument("--profit-weight", type=float, default=PROFIT_WEIGHT,
                       help="Weight for profit in scoring")
    parser.add_argument("--volume-weight", type=float, default=VOLUME_WEIGHT,
                       help="Weight for volume in scoring")
    parser.add_argument("--profit-margin-weight", type=float, default=PROFIT_MARGIN_WEIGHT,
                       help="Weight for profit margin in scoring")
    parser.add_argument("--conservative-pricing", action="store_true",
                       help="Use conservative pricing (P25 sell, P75 buy)")
    parser.add_argument("--robust-score", action="store_true",
                       help="Use robust (rank-based) scoring")
    parser.add_argument("--debug", action="store_true",
                       help="Enable debug logging")
    
    args = parser.parse_args()
    
    # Update global config
    HEADERS["Platform"] = args.platform
    PROFIT_WEIGHT = args.profit_weight
    VOLUME_WEIGHT = args.volume_weight
    PROFIT_MARGIN_WEIGHT = args.profit_margin_weight
    DEBUG_MODE = args.debug
    
    if DEBUG_MODE:
        logger.setLevel(logging.DEBUG)
    
    async def main():
        analyzer = SetProfitAnalyzer()
        await analyzer.initialize()
        try:
            await analyzer.analyze_all_sets(
                conservative_pricing=args.conservative_pricing,
                robust_score=args.robust_score,
            )
            analyzer.save_results()
            analyzer.generate_scatter_plot()
            print(f"Analysis complete! Results saved to {OUTPUT_FILE}")
        finally:
            await analyzer.close()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nAnalysis cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    cli_entry()
