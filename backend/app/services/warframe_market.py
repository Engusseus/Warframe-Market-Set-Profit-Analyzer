"""Warframe Market API service.

Async service for interacting with the Warframe Market API.
"""
import asyncio
import statistics
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

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
            max_requests=3,
            time_window=1.0
        )
        # Keep worker concurrency aligned with strict global API cap.
        self.max_concurrent_requests = 3
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

    async def _map_with_concurrency(
        self,
        items: List[Any],
        worker: Callable[[Any], Awaitable[Any]],
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        progress_message: Optional[Callable[[Any], str]] = None
    ) -> List[Any]:
        """Process items with bounded concurrency while preserving order."""
        if not items:
            return []

        logger = get_logger()
        semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        progress_lock = asyncio.Lock()
        total = len(items)
        completed = 0
        results: List[Any] = [None] * total

        async def _run(index: int, item: Any) -> None:
            nonlocal completed
            try:
                async with semaphore:
                    results[index] = await worker(item)
            except Exception as e:
                logger.warning(f"Concurrent worker failed for {item!r}: {e}")
                results[index] = None
            finally:
                if progress_callback:
                    async with progress_lock:
                        completed += 1
                        message = progress_message(item) if progress_message else "Processing..."
                        progress_callback(completed, total, message)

        await asyncio.gather(*(_run(i, item) for i, item in enumerate(items)))
        return results

    async def _fetch_part_quantities(
        self,
        part_codes: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """Fetch part quantity metadata once per unique part code."""
        unique_codes: List[str] = []
        seen_codes = set()
        for code in part_codes:
            if code and code not in seen_codes:
                seen_codes.add(code)
                unique_codes.append(code)

        async def _fetch(code: str) -> Dict[str, Any]:
            return await self.fetch_part_quantity(code)

        part_infos = await self._map_with_concurrency(unique_codes, _fetch)
        part_lookup: Dict[str, Dict[str, Any]] = {}
        for code, info in zip(unique_codes, part_infos):
            if isinstance(info, dict):
                part_lookup[code] = info
        return part_lookup

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

            except httpx.HTTPStatusError as e:
                logger.warning(f"HTTP Status Error on {url}: {e.response.status_code}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"All retries failed for {url} due to HTTP status error")
                    return None
            except httpx.RequestError as e:
                logger.error(f"Request error on {url}: {e}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"All retries failed for {url} due to request error")
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

        lowest = min(prices)
        highest = max(prices)
        count = len(prices)
        stats = {
            'lowest': lowest,
            'mean': statistics.fmean(prices),
            'min': lowest,
            'max': highest,
            'count': count
        }

        if count > 1:
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
        items = data.get("data") if isinstance(data, dict) else None
        if not isinstance(items, list):
            logger.error("Invalid item list payload from Warframe Market API")
            raise Exception("Invalid item list payload from API")

        from ..models.warframe_market import WFMItem

        logger.debug(f"API returned {len(items)} total items")
        prime_sets: List[Dict[str, Any]] = []
        skipped_malformed_prime_sets = 0

        for raw_item in items:
            if not isinstance(raw_item, dict):
                continue

            slug = raw_item.get("slug")
            if not isinstance(slug, str) or not slug.endswith("_prime_set"):
                continue

            try:
                parsed_item = WFMItem.model_validate(raw_item)
                prime_sets.append(parsed_item.model_dump(by_alias=True))
            except Exception as e:
                skipped_malformed_prime_sets += 1
                logger.warning(f"Skipping malformed prime set item {slug!r}: {e}")

        if skipped_malformed_prime_sets:
            logger.warning(
                f"Skipped {skipped_malformed_prime_sets} malformed prime set items from /items payload"
            )

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
            from ..models.warframe_market import WFMItemDetailResponse
            parsed = WFMItemDetailResponse.model_validate(data)
            item = parsed.data

            # Extract setParts and id
            # Remove the original prime_set ID from setParts if it exists
            filtered_set_parts = [part for part in (item.set_parts or []) if part != item.id]

            return {
                "id": item.id,
                "setParts": filtered_set_parts,
                "name": item.name
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
            from ..models.warframe_market import WFMItemDetailResponse
            parsed = WFMItemDetailResponse.model_validate(data)
            item = parsed.data
            return {
                "code": part_code,
                "name": item.name,
                "quantityInSet": item.quantity_in_set
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

        part_lookup = await self._fetch_part_quantities(set_details['setParts'])
        parts_with_quantities = [
            dict(part_lookup.get(
                part_code,
                {
                    "code": part_code,
                    "name": part_code.replace('_', ' ').title(),
                    "quantityInSet": 1
                }
            ))
            for part_code in set_details['setParts']
        ]

        return {
            'id': set_details['id'],
            'name': set_details['name'],
            'slug': slug,
            'setParts': parts_with_quantities
        }

    @staticmethod
    def _normalize_order_quantity(raw_quantity: Any) -> int:
        """Normalize API order quantity values."""
        try:
            quantity = int(float(raw_quantity))
        except (TypeError, ValueError):
            return 1
        return quantity if quantity > 0 else 1

    def _extract_order_levels(
        self,
        orders: List[Any]
    ) -> Tuple[List[float], List[Dict[str, Any]]]:
        """Extract valid prices and order levels from parsed API orders."""
        prices: List[float] = []
        levels: List[Dict[str, Any]] = []

        for order in orders:
            price = float(order.platinum)
            if price <= 0:
                continue

            quantity = self._normalize_order_quantity(getattr(order, "quantity", 1))
            prices.append(price)
            levels.append({
                "platinum": price,
                "quantity": quantity
            })

        return prices, levels

    async def fetch_item_orderbook(self, item_identifier: str) -> Dict[str, Any]:
        """Fetch top sell/buy orders with quantity for a specific item."""
        url = f"{self.v2_url}/orders/item/{item_identifier}/top"
        response = await self._fetch_with_retry(url)

        empty_result = {
            "sell_prices": [],
            "buy_prices": [],
            "top_sell_orders": [],
            "top_buy_orders": [],
            "lowest_price": 0.0,
            "highest_bid": 0.0,
        }
        if response is None:
            return empty_result

        try:
            data = response.json()
            from ..models.warframe_market import WFMOrdersResponse
            parsed = WFMOrdersResponse.model_validate(data)

            sell_prices, top_sell_orders = self._extract_order_levels(parsed.data.sell)
            buy_prices, top_buy_orders = self._extract_order_levels(parsed.data.buy)

            return {
                "sell_prices": sell_prices,
                "buy_prices": buy_prices,
                "top_sell_orders": top_sell_orders,
                "top_buy_orders": top_buy_orders,
                "lowest_price": min(sell_prices) if sell_prices else 0.0,
                "highest_bid": max(buy_prices) if buy_prices else 0.0,
            }
        except Exception:
            return empty_result

    async def fetch_item_prices(self, item_identifier: str) -> List[float]:
        """Fetch top sell orders for a specific item.

        Args:
            item_identifier: Item slug or ID

        Returns:
            List of platinum prices
        """
        orderbook = await self.fetch_item_orderbook(item_identifier)
        return orderbook.get("sell_prices", [])

    async def fetch_set_lowest_prices(
        self,
        detailed_sets: List[Dict[str, Any]],
        progress_callback: Optional[Callable] = None
    ) -> List[Dict[str, Any]]:
        """Fetch lowest prices for all Prime sets.

        Args:
            detailed_sets: List of detailed set information
            progress_callback: Optional callback for progress updates

        Returns:
            List of set pricing data
        """
        async def _fetch_for_set(set_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            set_name = set_data.get('name', 'Unknown Set')
            set_id = set_data.get('id', '')
            set_slug = set_data.get('slug', '')

            if not set_slug:
                return None

            orderbook = await self.fetch_item_orderbook(set_slug)
            prices = orderbook.get("sell_prices", [])
            if not prices:
                return None

            stats = self._calculate_pricing_statistics(prices)
            return {
                'slug': set_slug,
                'name': set_name,
                'id': set_id,
                'lowest_price': stats['lowest'],
                'highest_bid': orderbook.get('highest_bid', 0.0),
                'price_count': stats['count'],
                'min_price': stats['min'],
                'max_price': stats['max'],
                'top_sell_orders': orderbook.get('top_sell_orders', []),
                'top_buy_orders': orderbook.get('top_buy_orders', []),
            }

        results = await self._map_with_concurrency(
            detailed_sets,
            _fetch_for_set,
            progress_callback=progress_callback,
            progress_message=lambda s: f"Fetching prices for {s.get('name', 'Unknown Set')}"
        )
        return [item for item in results if item]

    async def fetch_part_lowest_prices(
        self,
        detailed_sets: List[Dict[str, Any]],
        progress_callback: Optional[Callable] = None
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

        async def _fetch_for_part(part: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            part_code = part.get('code', '')
            part_name = part.get('name', 'Unknown Part')
            if not part_code:
                return None

            orderbook = await self.fetch_item_orderbook(part_code)
            prices = orderbook.get("sell_prices", [])
            if not prices:
                return None

            stats = self._calculate_pricing_statistics(prices)
            return {
                'slug': part_code,
                'name': part_name,
                'lowest_price': stats['lowest'],
                'highest_bid': orderbook.get('highest_bid', 0.0),
                'price_count': stats['count'],
                'min_price': stats['min'],
                'max_price': stats['max'],
                'quantity_in_set': part.get('quantityInSet', 1),
                'top_sell_orders': orderbook.get('top_sell_orders', []),
                'top_buy_orders': orderbook.get('top_buy_orders', []),
            }

        results = await self._map_with_concurrency(
            all_parts,
            _fetch_for_part,
            progress_callback=progress_callback,
            progress_message=lambda p: f"Fetching prices for {p.get('name', 'Unknown Part')}"
        )
        return [item for item in results if item]

    async def fetch_set_volume(
        self,
        detailed_sets: List[Dict[str, Any]],
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Fetch 48-hour volume for all Prime sets.

        Args:
            detailed_sets: List of detailed set information
            progress_callback: Optional callback for progress updates

        Returns:
            Dict with 'individual' volumes and 'total'
        """
        async def _fetch_volume_for_set(
            set_data: Dict[str, Any]
        ) -> Optional[Tuple[str, float]]:
            set_slug = set_data.get('slug', '')
            if not set_slug:
                return None

            url = f"{self.v1_url}/items/{set_slug}/statistics"
            response = await self._fetch_with_retry(url)
            if response is None:
                return (set_slug, 0)

            try:
                data = response.json()
                from ..models.warframe_market import WFMStatisticsResponse
                parsed = WFMStatisticsResponse.model_validate(data)
                
                hours_48_data = parsed.payload.statistics_closed.hours48

                set_volume = 0.0
                for entry in hours_48_data:
                    if entry.volume >= 0:
                        set_volume += entry.volume

                return (set_slug, set_volume)
            except Exception:
                return (set_slug, 0)

        results = await self._map_with_concurrency(
            detailed_sets,
            _fetch_volume_for_set,
            progress_callback=progress_callback,
            progress_message=lambda s: f"Fetching volume for {s.get('name', 'Unknown Set')}"
        )

        volume_data: Dict[str, float] = {}
        total_volume = 0.0
        for item in results:
            if not item:
                continue
            slug, set_volume = item
            volume_data[slug] = set_volume
            total_volume += set_volume

        return {'individual': volume_data, 'total': total_volume}

    async def fetch_complete_set_data(
        self,
        prime_sets: List[Dict[str, Any]],
        progress_callback: Optional[Callable] = None
    ) -> List[Dict[str, Any]]:
        """Fetch complete detailed information for all sets.

        This is the slow path when cache is invalid.

        Args:
            prime_sets: List of prime sets from API
            progress_callback: Optional callback for progress updates

        Returns:
            List of detailed set data with parts
        """
        detailed_sets: List[Dict[str, Any]] = []

        # Sort alphabetically
        prime_sets_sorted = sorted(
            prime_sets,
            key=lambda x: x.get('i18n', {}).get('en', {}).get('name', x.get('slug', ''))
        )

        async def _fetch_details(item: Dict[str, Any]) -> Dict[str, Any]:
            slug = item.get('slug', '')
            details = await self.fetch_set_details(slug) if slug else None
            return {
                "slug": slug,
                "details": details,
                "item": item
            }

        detail_results = await self._map_with_concurrency(
            prime_sets_sorted,
            _fetch_details,
            progress_callback=progress_callback,
            progress_message=lambda item: f"Fetching details for {item.get('slug', '')}"
        )

        detail_lookup: Dict[str, Dict[str, Any]] = {}
        all_part_codes: List[str] = []
        for result in detail_results:
            if not result:
                continue
            slug = result.get("slug", "")
            details = result.get("details")
            if slug and details:
                detail_lookup[slug] = details
                all_part_codes.extend(details.get('setParts', []))

        part_lookup = await self._fetch_part_quantities(all_part_codes)

        for item in prime_sets_sorted:
            slug = item.get('slug', '')
            set_details = detail_lookup.get(slug)
            if set_details:
                parts_with_quantities = [
                    dict(part_lookup.get(
                        part_code,
                        {
                            "code": part_code,
                            "name": part_code.replace('_', ' ').title(),
                            "quantityInSet": 1
                        }
                    ))
                    for part_code in set_details.get('setParts', [])
                ]

                detailed_sets.append({
                    'id': set_details.get('id', ''),
                    'name': set_details.get('name', slug.replace('_', ' ').title()),
                    'slug': slug,
                    'setParts': parts_with_quantities
                })
            else:
                # Fallback for unavailable details
                i18n = item.get('i18n', {})
                en_info = i18n.get('en', {})
                name = en_info.get('name', slug.replace('_', ' ').title())
                detailed_sets.append({
                    'id': '',
                    'name': name,
                    'slug': slug,
                    'setParts': []
                })

        return detailed_sets
