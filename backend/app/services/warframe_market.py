"""Warframe Market API service.

Async service for interacting with the Warframe Market API.
"""
import asyncio
import statistics
from typing import Any, Dict, List, Optional, Tuple

import httpx

from ..config import get_settings
from ..core.logging import get_logger
from ..core.rate_limiter import RateLimiter


class WarframeMarketService:
    """Async service for Warframe Market API interactions."""

    def __init__(
        self,
        rate_limiter: Optional[RateLimiter] = None,
        http_client: Optional[httpx.AsyncClient] = None
    ):
        """Initialize the service.

        Args:
            rate_limiter: Rate limiter instance (creates default if None)
            http_client: HTTP client (creates default if None)
        """
        settings = get_settings()
        self.base_url = settings.warframe_market_base_url
        self.v1_url = settings.warframe_market_v1_url
        self.v2_url = settings.warframe_market_v2_url
        self.timeout = settings.request_timeout

        self.rate_limiter = rate_limiter or RateLimiter(
            max_requests=settings.rate_limit_requests,
            time_window=settings.rate_limit_window
        )
        self._client = http_client
        self._owns_client = http_client is None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def close(self) -> None:
        """Close HTTP client if we own it."""
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _fetch_with_retry(
        self,
        url: str,
        max_retries: int = 3
    ) -> Optional[httpx.Response]:
        """Fetch URL with exponential backoff retry logic.

        Args:
            url: URL to fetch
            max_retries: Maximum retry attempts

        Returns:
            Response or None if all retries failed
        """
        logger = get_logger()
        client = await self._get_client()

        for attempt in range(max_retries):
            try:
                await self.rate_limiter.wait_if_needed()
                logger.debug(f"Fetching: {url} (attempt {attempt + 1}/{max_retries})")
                response = await client.get(url)

                if response.status_code == 200:
                    return response
                elif response.status_code == 429:  # Rate limited
                    wait_time = 2 ** attempt
                    logger.warning(f"Rate limited (429) on {url}, waiting {wait_time}s")
                    await asyncio.sleep(wait_time)
                    continue
                elif response.status_code == 404:
                    logger.debug(f"Not found (404): {url}")
                    return None
                else:
                    logger.warning(f"HTTP {response.status_code} on {url}")
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        await asyncio.sleep(wait_time)
                    continue

            except httpx.TimeoutException as e:
                logger.warning(f"Timeout on {url}: {e}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"All retries failed for {url} due to timeout")
                    return None
            except httpx.ConnectError as e:
                logger.error(f"Connection error on {url}: {e}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"All retries failed for {url} due to connection error")
                    return None
            except Exception as e:
                logger.error(f"Error fetching {url}: {type(e).__name__}: {e}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"All retries failed for {url}")
                    return None

        logger.error(f"All retries exhausted for {url}")
        return None

    def _calculate_pricing_statistics(self, prices: List[float]) -> Dict[str, Any]:
        """Calculate comprehensive pricing statistics."""
        if not prices:
            return {
                'lowest': 0,
                'mean': 0,
                'std_dev': 0,
                'min': 0,
                'max': 0,
                'count': 0
            }

        stats = {
            'lowest': min(prices),
            'mean': statistics.mean(prices),
            'min': min(prices),
            'max': max(prices),
            'count': len(prices)
        }

        if len(prices) > 1:
            stats['std_dev'] = statistics.stdev(prices)
        else:
            stats['std_dev'] = 0

        return stats

    async def fetch_prime_sets(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetch list of all Prime sets from API.

        Args:
            limit: Optional limit on number of sets to return (for testing)

        Returns:
            List of Prime set items
        """
        logger = get_logger()
        url = f"{self.v2_url}/items"
        logger.info(f"Fetching Prime sets list from {url}")
        response = await self._fetch_with_retry(url)

        if response is None:
            logger.error("Failed to fetch items from Warframe Market API - response was None")
            raise Exception("Failed to fetch items from API")

        data = response.json()
        items = data.get("data", [])
        logger.debug(f"API returned {len(items)} total items")

        # Filter for items ending with 'prime_set'
        prime_sets = [
            item for item in items
            if item.get('slug', '').endswith('_prime_set')
        ]

        if not prime_sets:
            logger.error("No Prime sets found in API response")
            raise Exception("No Prime sets found")

        if limit:
            logger.info(f"Limiting to first {limit} Prime sets for testing")
            prime_sets = prime_sets[:limit]

        logger.info(f"Found {len(prime_sets)} Prime sets")
        return prime_sets

    async def fetch_set_details(self, slug: str) -> Optional[Dict[str, Any]]:
        """Fetch detailed information for a specific set.

        Args:
            slug: Set slug identifier

        Returns:
            Set details or None if not found
        """
        url = f"{self.v2_url}/item/{slug}"
        response = await self._fetch_with_retry(url)

        if response is None:
            return None

        try:
            data = response.json()
            item_data = data.get("data", {})

            # Extract setParts and id
            set_parts = item_data.get("setParts", [])
            item_id = item_data.get("id", "")

            # Remove the original prime_set ID from setParts if it exists
            filtered_set_parts = [part for part in set_parts if part != item_id]

            return {
                "id": item_id,
                "setParts": filtered_set_parts,
                "name": item_data.get("i18n", {}).get("en", {}).get(
                    "name", slug.replace('_', ' ').title()
                )
            }
        except Exception:
            return None

    async def fetch_part_quantity(self, part_code: str) -> Dict[str, Any]:
        """Fetch quantityInSet for a specific part.

        Args:
            part_code: Part identifier

        Returns:
            Part info with quantity
        """
        url = f"{self.v2_url}/item/{part_code}"
        response = await self._fetch_with_retry(url)

        if response is None:
            return {
                "code": part_code,
                "name": part_code.replace('_', ' ').title(),
                "quantityInSet": 1
            }

        try:
            data = response.json()
            item_data = data.get("data", {})
            quantity_in_set = item_data.get("quantityInSet", 1)
            part_name = item_data.get("i18n", {}).get("en", {}).get(
                "name", part_code.replace('_', ' ').title()
            )
            return {
                "code": part_code,
                "name": part_name,
                "quantityInSet": quantity_in_set
            }
        except Exception:
            return {
                "code": part_code,
                "name": part_code.replace('_', ' ').title(),
                "quantityInSet": 1
            }

    async def fetch_single_set_for_canary(self, slug: str) -> Optional[Dict[str, Any]]:
        """Fetch a single set's details for canary validation.

        This is a lightweight fetch used to validate cache integrity.
        Fetches set details and part quantities for comparison against cache.

        Args:
            slug: Set slug identifier

        Returns:
            Set data in same format as cached data, or None if fetch failed
        """
        logger = get_logger()
        logger.debug(f"Canary check: fetching details for {slug}")

        set_details = await self.fetch_set_details(slug)
        if set_details is None:
            logger.warning(f"Canary check: failed to fetch set details for {slug}")
            return None

        # Fetch part quantities (same as in fetch_complete_set_data)
        parts_with_quantities = []
        for part_code in set_details['setParts']:
            part_info = await self.fetch_part_quantity(part_code)
            parts_with_quantities.append(part_info)

        return {
            'id': set_details['id'],
            'name': set_details['name'],
            'slug': slug,
            'setParts': parts_with_quantities
        }

    async def fetch_item_prices(self, item_identifier: str) -> List[float]:
        """Fetch top sell orders for a specific item.

        Args:
            item_identifier: Item slug or ID

        Returns:
            List of platinum prices
        """
        url = f"{self.v2_url}/orders/item/{item_identifier}/top"
        response = await self._fetch_with_retry(url)

        if response is None:
            return []

        try:
            data = response.json()
            if not isinstance(data, dict) or 'data' not in data:
                return []

            orders_data = data.get("data", {})
            if not isinstance(orders_data, dict):
                return []

            sell_orders = orders_data.get("sell", [])
            if not isinstance(sell_orders, list):
                return []

            # Extract and validate prices
            sell_prices = []
            for order in sell_orders:
                if isinstance(order, dict):
                    platinum = order.get("platinum")
                    if isinstance(platinum, (int, float)) and platinum > 0:
                        sell_prices.append(platinum)

            return sell_prices
        except Exception:
            return []

    async def fetch_set_lowest_prices(
        self,
        detailed_sets: List[Dict[str, Any]],
        progress_callback: Optional[callable] = None
    ) -> List[Dict[str, Any]]:
        """Fetch lowest prices for all Prime sets.

        Args:
            detailed_sets: List of detailed set information
            progress_callback: Optional callback for progress updates

        Returns:
            List of set pricing data
        """
        lowest_prices = []
        total = len(detailed_sets)

        for i, set_data in enumerate(detailed_sets):
            set_name = set_data.get('name', 'Unknown Set')
            set_id = set_data.get('id', '')
            set_slug = set_data.get('slug', '')

            if not set_slug:
                continue

            if progress_callback:
                progress_callback(i + 1, total, f"Fetching prices for {set_name}")

            prices = await self.fetch_item_prices(set_slug)

            if prices:
                stats = self._calculate_pricing_statistics(prices)
                lowest_prices.append({
                    'slug': set_slug,
                    'name': set_name,
                    'id': set_id,
                    'lowest_price': stats['lowest'],
                    'price_count': stats['count'],
                    'min_price': stats['min'],
                    'max_price': stats['max']
                })

        return lowest_prices

    async def fetch_part_lowest_prices(
        self,
        detailed_sets: List[Dict[str, Any]],
        progress_callback: Optional[callable] = None
    ) -> List[Dict[str, Any]]:
        """Fetch lowest prices for all Prime parts.

        Args:
            detailed_sets: List of detailed set information
            progress_callback: Optional callback for progress updates

        Returns:
            List of part pricing data
        """
        # Deduplicate parts by code
        unique_parts = {}
        for set_data in detailed_sets:
            parts = set_data.get('setParts', [])
            for part in parts:
                part_code = part.get('code')
                if part_code and part_code not in unique_parts:
                    unique_parts[part_code] = part

        all_parts = list(unique_parts.values())
        part_lowest_prices = []
        total = len(all_parts)

        for i, part in enumerate(all_parts):
            part_code = part.get('code', '')
            part_name = part.get('name', 'Unknown Part')

            if not part_code:
                continue

            if progress_callback:
                progress_callback(i + 1, total, f"Fetching prices for {part_name}")

            prices = await self.fetch_item_prices(part_code)

            if prices:
                stats = self._calculate_pricing_statistics(prices)
                part_lowest_prices.append({
                    'slug': part_code,
                    'name': part_name,
                    'lowest_price': stats['lowest'],
                    'price_count': stats['count'],
                    'min_price': stats['min'],
                    'max_price': stats['max'],
                    'quantity_in_set': part.get('quantityInSet', 1)
                })

        return part_lowest_prices

    async def fetch_set_volume(
        self,
        detailed_sets: List[Dict[str, Any]],
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """Fetch 48-hour volume for all Prime sets.

        Args:
            detailed_sets: List of detailed set information
            progress_callback: Optional callback for progress updates

        Returns:
            Dict with 'individual' volumes and 'total'
        """
        volume_data = {}
        total_volume = 0
        total = len(detailed_sets)

        for i, set_data in enumerate(detailed_sets):
            set_name = set_data.get('name', 'Unknown Set')
            set_slug = set_data.get('slug', '')

            if not set_slug:
                continue

            if progress_callback:
                progress_callback(i + 1, total, f"Fetching volume for {set_name}")

            # Use v1 statistics endpoint
            url = f"{self.v1_url}/items/{set_slug}/statistics"
            response = await self._fetch_with_retry(url)

            if response is None:
                volume_data[set_slug] = 0
                continue

            try:
                data = response.json()
                payload = data.get("payload", {})
                statistics_closed = payload.get("statistics_closed", {})
                hours_48_data = statistics_closed.get("48hours", [])

                # Sum up all volume values from 48hours data
                set_volume = 0
                for entry in hours_48_data:
                    if isinstance(entry, dict):
                        volume = entry.get("volume", 0)
                        if isinstance(volume, (int, float)) and volume >= 0:
                            set_volume += volume

                volume_data[set_slug] = set_volume
                total_volume += set_volume
            except Exception:
                volume_data[set_slug] = 0

        return {'individual': volume_data, 'total': total_volume}

    async def fetch_complete_set_data(
        self,
        prime_sets: List[Dict[str, Any]],
        progress_callback: Optional[callable] = None
    ) -> List[Dict[str, Any]]:
        """Fetch complete detailed information for all sets.

        This is the slow path when cache is invalid.

        Args:
            prime_sets: List of prime sets from API
            progress_callback: Optional callback for progress updates

        Returns:
            List of detailed set data with parts
        """
        detailed_sets = []
        total = len(prime_sets)

        # Sort alphabetically
        prime_sets_sorted = sorted(
            prime_sets,
            key=lambda x: x.get('i18n', {}).get('en', {}).get('name', x.get('slug', ''))
        )

        for i, item in enumerate(prime_sets_sorted):
            slug = item.get('slug', '')

            if progress_callback:
                progress_callback(i + 1, total, f"Fetching details for {slug}")

            set_details = await self.fetch_set_details(slug)

            if set_details:
                # Fetch part quantities
                parts_with_quantities = []
                for part_code in set_details['setParts']:
                    part_info = await self.fetch_part_quantity(part_code)
                    parts_with_quantities.append(part_info)

                complete_set_data = {
                    'id': set_details['id'],
                    'name': set_details['name'],
                    'slug': slug,
                    'setParts': parts_with_quantities
                }
                detailed_sets.append(complete_set_data)
            else:
                # Fallback for unavailable details
                i18n = item.get('i18n', {})
                en_info = i18n.get('en', {})
                name = en_info.get('name', slug.replace('_', ' ').title())
                fallback_data = {
                    'id': '',
                    'name': name,
                    'slug': slug,
                    'setParts': []
                }
                detailed_sets.append(fallback_data)

        return detailed_sets
