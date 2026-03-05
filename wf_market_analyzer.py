#!/usr/bin/env python3
"""CLI analyzer for ranking profitable Warframe Prime sets."""

from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

import httpx

from config import (
    API_V1_URL,
    API_V2_URL,
    DEBUG_MODE,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_OUTPUT_PREFIX,
    HEADERS,
    LOG_FILE,
    MAX_RETRIES,
    PRICE_SAMPLE_SIZE,
    PROFIT_WEIGHT,
    REQUESTS_PER_SECOND,
    REQUEST_TIMEOUT_SECONDS,
    VOLUME_WEIGHT,
)


logger = logging.getLogger("wf_market_analyzer")
TOP_ORDER_SAMPLE_LIMIT = 5


@dataclass(slots=True)
class RuntimeConfig:
    """Resolved runtime settings for one analyzer run."""

    api_v1_url: str = API_V1_URL
    api_v2_url: str = API_V2_URL
    headers: dict[str, str] = field(default_factory=lambda: dict(HEADERS))
    requests_per_second: float = REQUESTS_PER_SECOND
    request_timeout_seconds: float = REQUEST_TIMEOUT_SECONDS
    max_retries: int = MAX_RETRIES
    output_dir: Path = field(default_factory=lambda: Path(DEFAULT_OUTPUT_DIR))
    output_prefix: str = DEFAULT_OUTPUT_PREFIX
    log_file: Path = field(default_factory=lambda: Path(LOG_FILE))
    debug: bool = DEBUG_MODE
    profit_weight: float = PROFIT_WEIGHT
    volume_weight: float = VOLUME_WEIGHT
    price_sample_size: int = PRICE_SAMPLE_SIZE


@dataclass(slots=True)
class SetData:
    """Metadata for one Prime set and its parts."""

    slug: str
    name: str
    parts: dict[str, int]
    part_names: dict[str, str]


@dataclass(slots=True)
class PriceData:
    """Computed pricing data for one Prime set."""

    set_price: float
    part_prices: dict[str, float]
    total_part_cost: float
    profit: float


@dataclass(slots=True)
class VolumeData:
    """Volume metrics for one Prime set."""

    volume_48h: int


@dataclass(slots=True)
class ResultRow:
    """Final ranked row written to the output CSV."""

    set_data: SetData
    price_data: PriceData
    volume_data: VolumeData
    score: float
    run_timestamp: str


def configure_logging(settings: RuntimeConfig) -> None:
    """Configure console and file logging."""

    settings.log_file.parent.mkdir(parents=True, exist_ok=True)
    handlers = [
        logging.StreamHandler(),
        logging.FileHandler(settings.log_file, encoding="utf-8"),
    ]
    logging.basicConfig(
        level=logging.DEBUG if settings.debug else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=handlers,
        force=True,
    )


def safe_float(value: Any, default: float = 0.0) -> float:
    """Convert an arbitrary value to float safely."""

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_positive_int(value: Any, default: int = 1) -> int:
    """Convert an arbitrary value to a positive int safely."""

    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def extract_item_name(item: dict[str, Any], fallback_slug: str) -> str:
    """Extract an English item name with sane fallbacks."""

    i18n = item.get("i18n")
    if isinstance(i18n, dict):
        english = i18n.get("en")
        if isinstance(english, dict):
            name = english.get("name")
            if isinstance(name, str) and name.strip():
                return name

    name = item.get("name")
    if isinstance(name, str) and name.strip():
        return name

    return fallback_slug.replace("_", " ").title()


def extract_set_items(payload: Any) -> list[dict[str, Any]]:
    """Normalize the v2 set payload into a list of items."""

    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if not isinstance(payload, dict):
        return []

    for key in ("items", "set"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]

    return []


def calculate_average_sell_price(prices: list[float], sample_size: int) -> float | None:
    """Average the lowest N positive sell prices."""

    valid_prices = sorted(price for price in prices if price > 0)
    if not valid_prices:
        return None

    take_count = min(max(sample_size, 1), len(valid_prices))
    selected = valid_prices[:take_count]
    return sum(selected) / len(selected)


def score_results(
    results: list[ResultRow],
    profit_weight: float,
    volume_weight: float,
) -> None:
    """Apply v0.1.0-style weighted min-max scoring in-place."""

    if not results:
        return

    profits = [row.price_data.profit for row in results]
    volumes = [row.volume_data.volume_48h for row in results]

    min_profit = min(profits)
    max_profit = max(profits)
    min_volume = min(volumes)
    max_volume = max(volumes)

    profit_range = max_profit - min_profit
    volume_range = max_volume - min_volume

    for row in results:
        normalized_profit = 0.0
        normalized_volume = 0.0

        if profit_range > 0:
            normalized_profit = (row.price_data.profit - min_profit) / profit_range
        if volume_range > 0:
            normalized_volume = (row.volume_data.volume_48h - min_volume) / volume_range

        row.score = (
            normalized_profit * profit_weight
            + normalized_volume * volume_weight
        )


def format_part_prices(result: ResultRow) -> str:
    """Format part prices for the CSV output."""

    formatted_parts: list[str] = []
    for part_slug, quantity in result.set_data.parts.items():
        part_name = result.set_data.part_names.get(part_slug, part_slug)
        part_price = result.price_data.part_prices.get(part_slug, 0.0)
        formatted_parts.append(f"{part_name} (x{quantity}): {part_price:.1f}")
    return "; ".join(formatted_parts)


def build_output_path(output_dir: Path, completed_at: datetime, prefix: str = DEFAULT_OUTPUT_PREFIX) -> Path:
    """Build a timestamped output path and avoid collisions."""

    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = f"{prefix}_{completed_at:%Y%m%d_%H%M%S}"
    candidate = output_dir / f"{base_name}.csv"
    suffix = 1

    while candidate.exists():
        candidate = output_dir / f"{base_name}_{suffix}.csv"
        suffix += 1

    return candidate


def write_results_to_csv(results: list[ResultRow], output_path: Path) -> None:
    """Write ranked results to a CSV file."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "Run Timestamp",
        "Set Name",
        "Set Slug",
        "Profit",
        "Set Selling Price",
        "Part Costs Total",
        "Volume (48h)",
        "Score",
        "Part Prices",
    ]

    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()

        for result in results:
            writer.writerow(
                {
                    "Run Timestamp": result.run_timestamp,
                    "Set Name": result.set_data.name,
                    "Set Slug": result.set_data.slug,
                    "Profit": f"{result.price_data.profit:.1f}",
                    "Set Selling Price": f"{result.price_data.set_price:.1f}",
                    "Part Costs Total": f"{result.price_data.total_part_cost:.1f}",
                    "Volume (48h)": result.volume_data.volume_48h,
                    "Score": f"{result.score:.4f}",
                    "Part Prices": format_part_prices(result),
                }
            )


class WarframeMarketClient:
    """Minimal async client for Warframe Market v1/v2 endpoints."""

    def __init__(self, settings: RuntimeConfig, transport: Any = None):
        self.settings = settings
        self._client = httpx.AsyncClient(
            headers=settings.headers,
            timeout=settings.request_timeout_seconds,
            transport=transport,
        )
        self._last_request_time = 0.0
        self._request_interval = 1.0 / max(settings.requests_per_second, 0.1)

    async def close(self) -> None:
        """Close the underlying HTTP client."""

        await self._client.aclose()

    async def _rate_limit(self) -> None:
        """Respect the configured global request pace."""

        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < self._request_interval:
            await asyncio.sleep(self._request_interval - elapsed)
        self._last_request_time = time.monotonic()

    async def _get_json(self, url: str) -> dict[str, Any] | None:
        """Fetch JSON with retries for transient failures."""

        backoff_seconds = 1.0
        for attempt in range(1, self.settings.max_retries + 1):
            await self._rate_limit()
            try:
                response = await self._client.get(url)
            except httpx.HTTPError as exc:
                logger.warning(
                    "Request failed for %s on attempt %s/%s: %s",
                    url,
                    attempt,
                    self.settings.max_retries,
                    exc,
                )
                if attempt == self.settings.max_retries:
                    return None
                await asyncio.sleep(backoff_seconds)
                backoff_seconds *= 2
                continue

            if response.status_code == 200:
                try:
                    payload = response.json()
                except ValueError:
                    logger.error("Invalid JSON returned from %s", url)
                    return None
                if isinstance(payload, dict):
                    return payload
                logger.error("Unexpected JSON payload type from %s", url)
                return None

            if response.status_code in {429, 500, 502, 503, 504}:
                logger.warning(
                    "Transient HTTP %s from %s on attempt %s/%s",
                    response.status_code,
                    url,
                    attempt,
                    self.settings.max_retries,
                )
                if attempt == self.settings.max_retries:
                    return None
                await asyncio.sleep(backoff_seconds)
                backoff_seconds *= 2
                continue

            if response.status_code == 404:
                logger.info("Endpoint returned 404 for %s", url)
                return None

            logger.error(
                "Non-retryable HTTP %s from %s: %s",
                response.status_code,
                url,
                response.text,
            )
            return None

        return None

    async def fetch_all_prime_set_slugs(self) -> list[str]:
        """Fetch all Prime set slugs from the v2 item list."""

        data = await self._get_json(f"{self.settings.api_v2_url}/items")
        if not data or not isinstance(data.get("data"), list):
            raise RuntimeError("Failed to fetch the v2 item catalog")

        slugs: list[str] = []
        for item in data["data"]:
            if not isinstance(item, dict):
                continue
            slug = item.get("slug")
            if isinstance(slug, str) and slug.endswith("_prime_set"):
                slugs.append(slug)

        if not slugs:
            raise RuntimeError("No Prime set slugs were found in the v2 item catalog")
        return slugs

    async def fetch_set_data(self, set_slug: str) -> SetData | None:
        """Fetch the part list for one set from the v2 set endpoint."""

        data = await self._get_json(f"{self.settings.api_v2_url}/item/{set_slug}/set")
        if not data:
            return None

        set_items = extract_set_items(data.get("data"))
        if not set_items:
            return None

        set_name = set_slug.replace("_", " ").title()
        parts: dict[str, int] = {}
        part_names: dict[str, str] = {}

        for item in set_items:
            item_slug = item.get("slug")
            if not isinstance(item_slug, str):
                continue

            if item_slug == set_slug:
                set_name = extract_item_name(item, set_slug)
                continue

            parts[item_slug] = safe_positive_int(item.get("quantityInSet"), default=1)
            part_names[item_slug] = extract_item_name(item, item_slug)

        if not parts:
            logger.debug("Skipping %s because no parts were found in the set payload", set_slug)
            return None

        return SetData(
            slug=set_slug,
            name=set_name,
            parts=parts,
            part_names=part_names,
        )

    async def fetch_top_sell_prices(self, item_slug: str) -> list[float]:
        """Fetch top sell prices from the v2 top orderbook endpoint."""

        data = await self._get_json(f"{self.settings.api_v2_url}/orders/item/{item_slug}/top")
        if not data:
            return []

        payload = data.get("data")
        if not isinstance(payload, dict):
            return []

        sell_orders = payload.get("sell")
        if not isinstance(sell_orders, list):
            return []

        prices: list[float] = []
        for order in sell_orders:
            if not isinstance(order, dict):
                continue
            price = safe_float(order.get("platinum", order.get("price")), default=0.0)
            if price > 0:
                prices.append(price)
        return prices

    async def fetch_volume_48h(self, set_slug: str) -> int | None:
        """Fetch 48-hour set volume from the v1 statistics endpoint."""

        data = await self._get_json(f"{self.settings.api_v1_url}/items/{set_slug}/statistics")
        if not data:
            return None

        payload = data.get("payload")
        if not isinstance(payload, dict):
            return None

        statistics_closed = payload.get("statistics_closed")
        if not isinstance(statistics_closed, dict):
            return None

        hours_48 = statistics_closed.get("48hours", statistics_closed.get("hours48"))
        if not isinstance(hours_48, list):
            return None

        total_volume = 0
        for entry in hours_48:
            if not isinstance(entry, dict):
                continue
            total_volume += max(int(safe_float(entry.get("volume"), 0.0)), 0)
        return total_volume


class SetProfitAnalyzer:
    """Orchestrates the end-to-end set analysis flow."""

    def __init__(self, settings: RuntimeConfig, transport: Any = None):
        self.settings = settings
        self.client = WarframeMarketClient(settings, transport=transport)

    async def analyze(self) -> tuple[list[ResultRow], datetime]:
        """Run the complete analysis and return ranked results."""

        try:
            return await self._analyze()
        finally:
            await self.client.close()

    async def _analyze(self) -> tuple[list[ResultRow], datetime]:
        set_slugs = await self.client.fetch_all_prime_set_slugs()
        logger.info("Found %s Prime sets in the v2 catalog", len(set_slugs))

        set_catalog: list[SetData] = []
        for index, set_slug in enumerate(set_slugs, start=1):
            set_data = await self.client.fetch_set_data(set_slug)
            if set_data is not None:
                set_catalog.append(set_data)

            if index % 25 == 0 or index == len(set_slugs):
                logger.info("Fetched set metadata %s/%s", index, len(set_slugs))

        if not set_catalog:
            raise RuntimeError("No valid Prime set metadata could be loaded")

        unique_item_slugs = list(dict.fromkeys(
            [set_data.slug for set_data in set_catalog]
            + [part_slug for set_data in set_catalog for part_slug in set_data.parts]
        ))
        orderbook_prices: dict[str, list[float]] = {}

        logger.info("Fetching top sell prices for %s items", len(unique_item_slugs))
        for index, item_slug in enumerate(unique_item_slugs, start=1):
            orderbook_prices[item_slug] = await self.client.fetch_top_sell_prices(item_slug)
            if index % 50 == 0 or index == len(unique_item_slugs):
                logger.info("Fetched orderbooks %s/%s", index, len(unique_item_slugs))

        volumes: dict[str, int | None] = {}
        logger.info("Fetching 48-hour volume for %s sets", len(set_catalog))
        for index, set_data in enumerate(set_catalog, start=1):
            volumes[set_data.slug] = await self.client.fetch_volume_48h(set_data.slug)
            if index % 25 == 0 or index == len(set_catalog):
                logger.info("Fetched set volumes %s/%s", index, len(set_catalog))

        completed_at = datetime.now().astimezone().replace(microsecond=0)
        run_timestamp = completed_at.isoformat()
        results: list[ResultRow] = []

        for set_data in set_catalog:
            price_data = self._calculate_set_profit(set_data, orderbook_prices)
            volume = volumes.get(set_data.slug)

            if price_data is None:
                logger.debug("Skipping %s because pricing data was incomplete", set_data.slug)
                continue

            if volume is None:
                logger.debug("Skipping %s because 48-hour volume data was unavailable", set_data.slug)
                continue

            results.append(
                ResultRow(
                    set_data=set_data,
                    price_data=price_data,
                    volume_data=VolumeData(volume_48h=volume),
                    score=0.0,
                    run_timestamp=run_timestamp,
                )
            )

        if not results:
            raise RuntimeError("No analyzable sets were produced from the API responses")

        score_results(
            results,
            profit_weight=self.settings.profit_weight,
            volume_weight=self.settings.volume_weight,
        )
        results.sort(key=lambda row: row.score, reverse=True)

        logger.info("Analysis complete. Ranked %s sets.", len(results))
        return results, completed_at

    def _calculate_set_profit(
        self,
        set_data: SetData,
        orderbook_prices: dict[str, list[float]],
    ) -> PriceData | None:
        set_price = calculate_average_sell_price(
            orderbook_prices.get(set_data.slug, []),
            self.settings.price_sample_size,
        )
        if set_price is None:
            return None

        part_prices: dict[str, float] = {}
        total_part_cost = 0.0

        for part_slug, quantity in set_data.parts.items():
            part_price = calculate_average_sell_price(
                orderbook_prices.get(part_slug, []),
                self.settings.price_sample_size,
            )
            if part_price is None:
                return None

            part_prices[part_slug] = part_price
            total_part_cost += part_price * quantity

        return PriceData(
            set_price=set_price,
            part_prices=part_prices,
            total_part_cost=total_part_cost,
            profit=set_price - total_part_cost,
        )


def positive_int(value: str) -> int:
    """Argparse type for positive integers."""

    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return parsed


def price_sample_size_arg(value: str) -> int:
    """Argparse type for sample sizes supported by the v2 /top orderbook endpoint."""

    parsed = positive_int(value)
    if parsed > TOP_ORDER_SAMPLE_LIMIT:
        raise argparse.ArgumentTypeError(
            f"value must be between 1 and {TOP_ORDER_SAMPLE_LIMIT}"
        )
    return parsed


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Analyze Warframe Prime set profitability using v2 item/orderbook "
            "endpoints and the v1 statistics endpoint."
        )
    )
    parser.add_argument("--profit-weight", type=float, default=PROFIT_WEIGHT)
    parser.add_argument("--volume-weight", type=float, default=VOLUME_WEIGHT)
    parser.add_argument(
        "--price-sample-size",
        type=price_sample_size_arg,
        default=PRICE_SAMPLE_SIZE,
    )
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--debug", action="store_true", default=DEBUG_MODE)
    return parser.parse_args(argv)


def runtime_config_from_args(args: argparse.Namespace) -> RuntimeConfig:
    """Resolve runtime settings from CLI arguments."""

    return RuntimeConfig(
        output_dir=Path(args.output_dir),
        debug=bool(args.debug),
        profit_weight=float(args.profit_weight),
        volume_weight=float(args.volume_weight),
        price_sample_size=int(args.price_sample_size),
    )


async def run_analysis(
    settings: RuntimeConfig,
    transport: Any = None,
) -> tuple[Path, list[ResultRow]]:
    """Run analysis and persist the timestamped CSV output."""

    analyzer = SetProfitAnalyzer(settings, transport=transport)
    results, completed_at = await analyzer.analyze()
    output_path = build_output_path(
        settings.output_dir,
        completed_at,
        prefix=settings.output_prefix,
    )
    write_results_to_csv(results, output_path)
    return output_path, results


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint."""

    args = parse_args(argv)
    settings = runtime_config_from_args(args)
    configure_logging(settings)

    print("=== Warframe Market Set Profit Analyzer ===")
    print(f"Profit weight: {settings.profit_weight}")
    print(f"Volume weight: {settings.volume_weight}")
    print(f"Price sample size: {settings.price_sample_size}")
    print("Using v2 item/order endpoints and v1 statistics.")
    print("Starting analysis...")

    try:
        output_path, results = asyncio.run(run_analysis(settings))
    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
        return 130
    except Exception as exc:
        logger.error("Analyzer failed", exc_info=True)
        print(f"\nAnalysis failed: {exc}")
        print(f"Check {settings.log_file} for details.")
        return 1

    print(f"\nAnalysis complete. Ranked {len(results)} sets.")
    print(f"CSV written to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
