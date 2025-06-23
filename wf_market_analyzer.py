# Warframe Market Set Profit Analyzer
# Identifies profitable item sets based on a combined score of profit and trading volume

import asyncio
import aiohttp
import pandas as pd
import time
import json
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("wf_market_analyzer.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
API_BASE_URL = 'https://api.warframe.market'
REQUESTS_PER_SECOND = 3  # Rate limit to avoid API throttling
HEADERS = {
    'Platform': 'pc',
    'Language': 'en',
    'Accept': 'application/json',
    'Crossplay': 'true'  # Enable crossplay to get all relevant orders
}
OUTPUT_FILE = 'set_profit_analysis.csv'
DEBUG_MODE = True  # Enable detailed logging

# Weight for scoring calculation
PROFIT_WEIGHT = 1.0
VOLUME_WEIGHT = 1.2


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


@dataclass
class VolumeData:
    """Data structure to hold volume information"""
    volume_48h: int


@dataclass
class ResultData:
    """Combined results for a set"""
    set_data: SetData
    price_data: PriceData
    volume_data: VolumeData
    score: float


class WarframeMarketAPI:
    """Client for interacting with the Warframe Market API"""

    def __init__(self):
        """Initialize the API client with rate limiting"""
        self.session = None
        self.last_request_time = 0
        self.request_interval = 1.0 / REQUESTS_PER_SECOND
        self._lock = asyncio.Lock()

    async def initialize(self):
        """Create the HTTP session"""
        self.session = aiohttp.ClientSession(headers=HEADERS)

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
            await self._rate_limit()
            url = f"{API_BASE_URL}{endpoint}"

            try:
                if DEBUG_MODE:
                    logger.debug(f"Making request to: {url}")

                async with self.session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data
                    else:
                        error_text = await response.text()
                        logger.error(f"Error {response.status} from {url}: {error_text}")

                        # Handle specific error codes
                        if response.status == 429:  # Rate limited
                            wait_time = backoff * 10  # Longer backoff for rate limiting
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

    def __init__(self):
        """Initialize the analyzer"""
        self.api = WarframeMarketAPI()
        self.sets = {}  # slug -> SetData
        self.results = []  # List of ResultData

    async def initialize(self):
        """Initialize the API client"""
        await self.api.initialize()

    async def close(self):
        """Clean up resources"""
        await self.api.close()

    async def fetch_all_items(self) -> List[Dict]:
        """Fetch all tradable items from the API"""
        logger.info("Fetching all tradable items...")
        data = await self.api.get("/v2/items")

        if not data or 'data' not in data:
            logger.error("Failed to fetch items")
            return []

        return data['data']

    async def fetch_set_data(self, set_slug: str) -> Optional[SetData]:
        """
        Fetch set information for a given set slug

        Args:
            set_slug: Slug identifier for the set

        Returns:
            SetData object or None if the set could not be fetched
        """
        logger.info(f"Fetching set data for: {set_slug}")
        data = await self.api.get(f"/v2/item/{set_slug}/set")

        if not data or 'data' not in data or 'items' not in data['data']:
            logger.error(f"Failed to fetch set data for {set_slug}")
            return None

        # Extract relevant info from the response
        set_items = data['data']['items']
        set_name = None
        parts = {}
        part_names = {}

        # First, find the set itself to get the name
        for item in set_items:
            if item['slug'] == set_slug and 'i18n' in item and 'en' in item['i18n']:
                set_name = item['i18n']['en']['name']
                break

        if not set_name:
            logger.warning(f"Could not find name for set {set_slug}")
            set_name = set_slug  # Fallback to using the slug as name

        # Then process all parts
        for item in set_items:
            # Skip the set itself
            if item['slug'] == set_slug:
                continue

            # Get part quantity
            quantity = item.get('quantityInSet', 1)

            # Get part name
            part_name = item.get('i18n', {}).get('en', {}).get('name', item['slug'])

            parts[item['slug']] = quantity
            part_names[item['slug']] = part_name

        return SetData(
            slug=set_slug,
            name=set_name,
            parts=parts,
            part_names=part_names
        )

    async def fetch_orders(self, item_slug: str) -> List[Dict]:
        """
        Fetch orders for a specific item

        Args:
            item_slug: Slug identifier for the item

        Returns:
            List of orders for the item
        """
        logger.info(f"Fetching orders for: {item_slug}")
        data = await self.api.get(f"/v1/items/{item_slug}/orders")

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

    def calculate_average_price(self, orders: List[Dict], order_type: str, count: int = 2) -> Optional[float]:
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

    async def calculate_set_profit(self, set_data: SetData) -> Optional[PriceData]:
        """
        Calculate profit for a set

        Args:
            set_data: SetData object with set and part information

        Returns:
            PriceData object or None if prices could not be calculated
        """
        logger.info(f"Calculating profit for set: {set_data.name}")

        # Fetch set orders
        set_orders = await self.fetch_orders(set_data.slug)
        if not set_orders:
            logger.error(f"No orders found for set {set_data.slug}")
            return None

        # Calculate average selling price for the set (from lowest 2 sell orders)
        set_price = self.calculate_average_price(set_orders, 'sell')
        if set_price is None:
            logger.error(f"Could not calculate sell price for set {set_data.slug}")
            return None

        # Calculate part costs
        part_prices = {}
        total_part_cost = 0
        missing_parts = []

        for part_slug, quantity in set_data.parts.items():
            # Fetch part orders
            part_orders = await self.fetch_orders(part_slug)
            if not part_orders:
                logger.warning(f"No orders found for part {part_slug}")
                missing_parts.append(part_slug)
                continue

            # Calculate average selling price for the part (from lowest 2 sell orders)
            part_price = self.calculate_average_price(part_orders, 'sell')
            if part_price is None:
                logger.warning(f"Could not calculate price for part {part_slug}")
                missing_parts.append(part_slug)
                continue

            # Store part price
            part_prices[part_slug] = part_price

            # Add to total cost (accounting for quantity)
            total_part_cost += part_price * quantity

        # Skip sets with missing part prices
        if missing_parts:
            logger.warning(f"Skipping set {set_data.name} due to missing prices for parts: {missing_parts}")
            return None

        # Calculate profit
        profit = set_price - total_part_cost

        return PriceData(
            set_price=set_price,
            part_prices=part_prices,
            total_part_cost=total_part_cost,
            profit=profit
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

        # Use the statistics endpoint to get volume data
        data = await self.api.get(f"/v1/items/{set_slug}/statistics")

        volume_48h = 0

        if data and 'payload' in data and 'statistics_closed' in data['payload'] and '48hours' in data['payload'][
            'statistics_closed']:
            # Extract volume from 48-hour statistics
            for stat in data['payload']['statistics_closed']['48hours']:
                volume_48h += stat.get('volume', 0)

        if DEBUG_MODE:
            logger.debug(f"48-hour volume for {set_slug}: {volume_48h}")

        return VolumeData(volume_48h=volume_48h)

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

        # Extract profit and volume values
        profits = [r.price_data.profit for r in results]
        volumes = [r.volume_data.volume_48h for r in results]

        # Calculate min/max for normalization
        min_profit = min(profits)
        max_profit = max(profits)
        profit_range = max_profit - min_profit

        min_volume = min(volumes)
        max_volume = max(volumes)
        volume_range = max_volume - min_volume

        # Normalize and calculate scores
        for result in results:
            # Avoid division by zero
            norm_profit = 0 if profit_range == 0 else (result.price_data.profit - min_profit) / profit_range
            norm_volume = 0 if volume_range == 0 else (result.volume_data.volume_48h - min_volume) / volume_range

            # Calculate weighted score
            result.score = (norm_profit * PROFIT_WEIGHT) + (norm_volume * VOLUME_WEIGHT)

            if DEBUG_MODE:
                logger.debug(f"Set: {result.set_data.name}, Profit: {result.price_data.profit}, "
                             f"Volume: {result.volume_data.volume_48h}, Score: {result.score:.4f}")

        return results

    async def process_set(self, set_item: Dict) -> Optional[ResultData]:
        """Process a single set and return its analysis result"""
        set_slug = set_item['slug']

        # Fetch set data (parts and quantities)
        set_data = await self.fetch_set_data(set_slug)
        if not set_data:
            return None

        # Calculate profit
        price_data = await self.calculate_set_profit(set_data)
        if not price_data:
            return None

        # Fetch volume data
        volume_data = await self.fetch_volume_data(set_slug)

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

        # Filter to only include sets
        set_items = [item for item in items if 'set' in item.get('tags', [])]
        logger.info(f"Found {len(set_items)} sets to analyze")

        tasks = [asyncio.create_task(self.process_set(item)) for item in set_items]

        results = []
        for future in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="Analyzing sets"):
            result = await future
            if result:
                results.append(result)

        # Normalize data and calculate scores
        results = self.normalize_data(results)

        # Sort by score (descending)
        results.sort(key=lambda r: r.score, reverse=True)

        self.results = results
        logger.info(f"Analysis complete. Found {len(results)} profitable sets.")

    def save_to_csv(self):
        """Save results to CSV file"""
        logger.info(f"Saving results to {OUTPUT_FILE}")

        # Prepare data for CSV
        csv_data = []

        for result in self.results:
            # Build a string with all part prices
            part_prices_str = "; ".join([
                f"{result.set_data.part_names.get(slug, slug)} (x{qty}): {result.price_data.part_prices.get(slug, 0):.1f}"
                for slug, qty in result.set_data.parts.items()
            ])

            row = {
                'Set Name': result.set_data.name,
                'Profit': round(result.price_data.profit, 1),
                'Set Selling Price': round(result.price_data.set_price, 1),
                'Part Costs Total': round(result.price_data.total_part_cost, 1),
                'Volume (48h)': result.volume_data.volume_48h,
                'Score': round(result.score, 4),
                'Part Prices': part_prices_str
            }
            csv_data.append(row)

        # Create DataFrame and save to CSV
        df = pd.DataFrame(csv_data)
        df.to_csv(OUTPUT_FILE, index=False)
        logger.info(f"Results saved to {OUTPUT_FILE}")

        # Save detailed JSON for debugging
        if DEBUG_MODE:
            json_file = 'set_profit_analysis_detailed.json'

            # Convert dataclasses to dictionaries
            detailed_data = []

            for result in self.results:
                detailed_result = {
                    'set': {
                        'slug': result.set_data.slug,
                        'name': result.set_data.name,
                        'parts': {
                            slug: {
                                'quantity': qty,
                                'name': result.set_data.part_names.get(slug, slug),
                                'price': result.price_data.part_prices.get(slug, 0)
                            }
                            for slug, qty in result.set_data.parts.items()
                        }
                    },
                    'pricing': {
                        'set_price': result.price_data.set_price,
                        'total_part_cost': result.price_data.total_part_cost,
                        'profit': result.price_data.profit
                    },
                    'volume': {
                        'volume_48h': result.volume_data.volume_48h
                    },
                    'score': result.score
                }
                detailed_data.append(detailed_result)

            with open(json_file, 'w') as f:
                json.dump(detailed_data, f, indent=2)

            logger.info(f"Detailed results saved to {json_file}")


async def main():
    """Main entry point"""
    analyzer = SetProfitAnalyzer()

    try:
        await analyzer.initialize()
        await analyzer.analyze_all_sets()
        analyzer.save_to_csv()
    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}", exc_info=True)
    finally:
        await analyzer.close()


if __name__ == "__main__":
    print("=== Warframe Market Set Profit Analyzer ===")
    print(f"Output will be saved to: {OUTPUT_FILE}")
    print("Starting analysis...")

    asyncio.run(main())

    print("Analysis complete!")
