#!/usr/bin/env python3
"""CLI analyzer for ranking profitable Warframe Prime sets."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import math
import os
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Callable, Sequence

import httpx

from config import (
    ALLOW_THIN_ORDERBOOKS,
    API_V1_URL,
    API_V2_URL,
    APP_NAME,
    APP_VERSION,
    DEBUG_MODE,
    DEFAULT_CROSSPLAY,
    DEFAULT_LANGUAGE,
    DEFAULT_LOG_FILE,
    DEFAULT_LOG_LEVEL,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_OUTPUT_PREFIX,
    DEFAULT_PLATFORM,
    ENV_PREFIX,
    JSON_SUMMARY,
    LOG_BACKUP_COUNT,
    LOG_MAX_BYTES,
    MAX_RETRIES,
    PRICE_SAMPLE_SIZE,
    PROFIT_WEIGHT,
    REQUEST_TIMEOUT_SECONDS,
    REQUESTS_PER_SECOND,
    VOLUME_WEIGHT,
)

logger = logging.getLogger("wf_market_analyzer")
TOP_ORDER_SAMPLE_LIMIT = 5
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504, 509}


def generate_run_id() -> str:
    """Generate a short ID for correlating logs and outputs."""

    return uuid.uuid4().hex[:8]


def build_request_headers(platform: str, language: str, crossplay: bool) -> dict[str, str]:
    """Build request headers from the resolved runtime configuration."""

    return {
        "Platform": platform,
        "Language": language,
        "Crossplay": str(crossplay).lower(),
        "Accept": "application/json",
    }


class RunIdFilter(logging.Filter):
    """Attach the current run identifier to every log record."""

    def __init__(self, run_id: str):
        super().__init__()
        self.run_id = run_id

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "run_id"):
            record.run_id = self.run_id
        return True


@dataclass(slots=True)
class RuntimeConfig:
    """Resolved runtime settings for one analyzer run."""

    api_v1_url: str = API_V1_URL
    api_v2_url: str = API_V2_URL
    platform: str = DEFAULT_PLATFORM
    language: str = DEFAULT_LANGUAGE
    crossplay: bool = DEFAULT_CROSSPLAY
    requests_per_second: float = REQUESTS_PER_SECOND
    request_timeout_seconds: float = REQUEST_TIMEOUT_SECONDS
    max_retries: int = MAX_RETRIES
    output_dir: Path = field(default_factory=lambda: Path(DEFAULT_OUTPUT_DIR))
    output_prefix: str = DEFAULT_OUTPUT_PREFIX
    output_file: Path | None = None
    log_level: str = DEFAULT_LOG_LEVEL
    log_file: Path | None = DEFAULT_LOG_FILE
    log_max_bytes: int = LOG_MAX_BYTES
    log_backup_count: int = LOG_BACKUP_COUNT
    debug: bool = DEBUG_MODE
    json_summary: bool = JSON_SUMMARY
    allow_thin_orderbooks: bool = ALLOW_THIN_ORDERBOOKS
    profit_weight: float = PROFIT_WEIGHT
    volume_weight: float = VOLUME_WEIGHT
    price_sample_size: int = PRICE_SAMPLE_SIZE
    run_id: str = field(default_factory=generate_run_id)
    headers: dict[str, str] = field(init=False)

    def __post_init__(self) -> None:
        self.platform = self.platform.strip().lower()
        self.language = self.language.strip().lower()
        self.output_dir = Path(self.output_dir)
        self.output_file = Path(self.output_file) if self.output_file is not None else None
        self.log_file = Path(self.log_file) if self.log_file is not None else None
        if self.debug:
            self.log_level = "DEBUG"
        self.log_level = self.log_level.upper()
        self.headers = build_request_headers(
            platform=self.platform,
            language=self.language,
            crossplay=self.crossplay,
        )


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


@dataclass(slots=True)
class AnalysisReport:
    """Structured summary of a completed analysis run."""

    results: list[ResultRow]
    completed_at: datetime
    catalog_set_count: int
    metadata_set_count: int
    skipped_invalid_set_count: int
    skipped_missing_price_count: int
    skipped_missing_volume_count: int


def configure_logging(settings: RuntimeConfig) -> None:
    """Configure analyzer logging to stderr and an optional rotated log file."""

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(name)s] run_id=%(run_id)s %(message)s"
    )
    handlers: list[logging.Handler] = []
    run_id_filter = RunIdFilter(settings.run_id)

    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(run_id_filter)
    handlers.append(stream_handler)

    if settings.log_file is not None:
        settings.log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            settings.log_file,
            encoding="utf-8",
            maxBytes=settings.log_max_bytes,
            backupCount=settings.log_backup_count,
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(run_id_filter)
        handlers.append(file_handler)

    for handler in list(logger.handlers):
        handler.close()
    logger.handlers.clear()
    logger.setLevel(getattr(logging, settings.log_level, logging.INFO))
    logger.propagate = False
    for handler in handlers:
        logger.addHandler(handler)

    external_log_level = logging.DEBUG if settings.debug else logging.WARNING
    for logger_name in ("httpx", "httpcore"):
        logging.getLogger(logger_name).setLevel(external_log_level)


def safe_float(value: Any, default: float = 0.0) -> float:
    """Convert an arbitrary value to a finite float safely."""

    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(parsed):
        return default
    return parsed


def parse_required_positive_int(value: Any) -> int | None:
    """Parse a required positive integer-like value."""

    parsed = safe_float(value, default=math.nan)
    if not math.isfinite(parsed) or parsed <= 0 or not parsed.is_integer():
        return None
    return int(parsed)


def parse_required_non_negative_int(value: Any) -> int | None:
    """Parse a required non-negative integer-like value."""

    parsed = safe_float(value, default=math.nan)
    if not math.isfinite(parsed) or parsed < 0 or not parsed.is_integer():
        return None
    return int(parsed)


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


def calculate_average_sell_price(
    prices: list[float],
    sample_size: int,
    allow_thin_orderbooks: bool = False,
) -> float | None:
    """Average the lowest N positive sell prices."""

    valid_prices = sorted(price for price in prices if price > 0)
    if not valid_prices:
        return None

    required_sample_size = max(sample_size, 1)
    if not allow_thin_orderbooks and len(valid_prices) < required_sample_size:
        return None

    take_count = min(required_sample_size, len(valid_prices))
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


def build_output_path(
    output_dir: Path,
    completed_at: datetime,
    prefix: str = DEFAULT_OUTPUT_PREFIX,
    output_file: Path | None = None,
    run_id: str | None = None,
) -> Path:
    """Build the final output path for a run."""

    if output_file is not None:
        return Path(output_file)

    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = f"{prefix}_{completed_at:%Y%m%d_%H%M%S}"

    if run_id:
        return output_dir / f"{base_name}_{run_id}.csv"

    candidate = output_dir / f"{base_name}.csv"
    suffix = 1
    while candidate.exists():
        candidate = output_dir / f"{base_name}_{suffix}.csv"
        suffix += 1
    return candidate


def write_results_to_csv(results: list[ResultRow], output_path: Path) -> None:
    """Write ranked results to a CSV file atomically."""

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

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            newline="",
            encoding="utf-8",
            dir=output_path.parent,
            prefix=f".{output_path.stem}_",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
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

        temp_path.replace(output_path)
    except Exception:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        raise


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

            if response.status_code in RETRYABLE_STATUS_CODES:
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

            quantity = parse_required_positive_int(item.get("quantityInSet"))
            if quantity is None:
                logger.warning(
                    "Skipping %s because part %s had invalid quantityInSet=%r",
                    set_slug,
                    item_slug,
                    item.get("quantityInSet"),
                )
                return None

            parts[item_slug] = quantity
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
                logger.warning("Skipping %s because one volume entry was not an object", set_slug)
                return None

            volume = parse_required_non_negative_int(entry.get("volume"))
            if volume is None:
                logger.warning(
                    "Skipping %s because one volume entry had invalid volume=%r",
                    set_slug,
                    entry.get("volume"),
                )
                return None

            total_volume += volume
        return total_volume


class SetProfitAnalyzer:
    """Orchestrates the end-to-end set analysis flow."""

    def __init__(self, settings: RuntimeConfig, transport: Any = None):
        self.settings = settings
        self.client = WarframeMarketClient(settings, transport=transport)

    async def analyze(self) -> AnalysisReport:
        """Run the complete analysis and return a structured report."""

        try:
            return await self._analyze()
        finally:
            await self.client.close()

    async def _analyze(self) -> AnalysisReport:
        set_slugs = await self.client.fetch_all_prime_set_slugs()
        catalog_set_count = len(set_slugs)
        logger.info("Found %s Prime sets in the v2 catalog", catalog_set_count)

        set_catalog: list[SetData] = []
        for index, set_slug in enumerate(set_slugs, start=1):
            set_data = await self.client.fetch_set_data(set_slug)
            if set_data is not None:
                set_catalog.append(set_data)

            if index % 25 == 0 or index == catalog_set_count:
                logger.info("Fetched set metadata %s/%s", index, catalog_set_count)

        if not set_catalog:
            raise RuntimeError("No valid Prime set metadata could be loaded")

        metadata_set_count = len(set_catalog)
        skipped_invalid_set_count = catalog_set_count - metadata_set_count

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
        logger.info("Fetching 48-hour volume for %s sets", metadata_set_count)
        for index, set_data in enumerate(set_catalog, start=1):
            volumes[set_data.slug] = await self.client.fetch_volume_48h(set_data.slug)
            if index % 25 == 0 or index == metadata_set_count:
                logger.info("Fetched set volumes %s/%s", index, metadata_set_count)

        completed_at = datetime.now().astimezone().replace(microsecond=0)
        run_timestamp = completed_at.isoformat()
        results: list[ResultRow] = []
        skipped_missing_price_count = 0
        skipped_missing_volume_count = 0

        for set_data in set_catalog:
            price_data = self._calculate_set_profit(set_data, orderbook_prices)
            volume = volumes.get(set_data.slug)

            if price_data is None:
                skipped_missing_price_count += 1
                logger.debug("Skipping %s because pricing data was incomplete", set_data.slug)
                continue

            if volume is None:
                skipped_missing_volume_count += 1
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
            raise RuntimeError(
                "No analyzable sets were produced from the API responses "
                f"(missing_price={skipped_missing_price_count}, "
                f"missing_volume={skipped_missing_volume_count})"
            )

        score_results(
            results,
            profit_weight=self.settings.profit_weight,
            volume_weight=self.settings.volume_weight,
        )
        results.sort(key=lambda row: row.score, reverse=True)

        logger.info(
            "Analysis complete. Ranked %s sets (catalog=%s metadata=%s skipped_invalid=%s "
            "skipped_price=%s skipped_volume=%s)",
            len(results),
            catalog_set_count,
            metadata_set_count,
            skipped_invalid_set_count,
            skipped_missing_price_count,
            skipped_missing_volume_count,
        )
        return AnalysisReport(
            results=results,
            completed_at=completed_at,
            catalog_set_count=catalog_set_count,
            metadata_set_count=metadata_set_count,
            skipped_invalid_set_count=skipped_invalid_set_count,
            skipped_missing_price_count=skipped_missing_price_count,
            skipped_missing_volume_count=skipped_missing_volume_count,
        )

    def _calculate_set_profit(
        self,
        set_data: SetData,
        orderbook_prices: dict[str, list[float]],
    ) -> PriceData | None:
        set_price = calculate_average_sell_price(
            orderbook_prices.get(set_data.slug, []),
            self.settings.price_sample_size,
            allow_thin_orderbooks=self.settings.allow_thin_orderbooks,
        )
        if set_price is None:
            return None

        part_prices: dict[str, float] = {}
        total_part_cost = 0.0

        for part_slug, quantity in set_data.parts.items():
            part_price = calculate_average_sell_price(
                orderbook_prices.get(part_slug, []),
                self.settings.price_sample_size,
                allow_thin_orderbooks=self.settings.allow_thin_orderbooks,
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

    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("value must be an integer") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return parsed


def non_negative_int(value: str) -> int:
    """Argparse type for non-negative integers."""

    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("value must be an integer") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be zero or greater")
    return parsed


def positive_float(value: str) -> float:
    """Argparse type for finite positive floats."""

    parsed = safe_float(value, default=math.nan)
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a finite number greater than zero")
    return parsed


def non_negative_finite_float(value: str) -> float:
    """Argparse type for finite non-negative floats."""

    parsed = safe_float(value, default=math.nan)
    if not math.isfinite(parsed) or parsed < 0:
        raise argparse.ArgumentTypeError("value must be a finite number zero or greater")
    return parsed


def non_empty_string(value: str) -> str:
    """Argparse type for non-empty strings."""

    parsed = value.strip()
    if not parsed:
        raise argparse.ArgumentTypeError("value must not be empty")
    return parsed


def log_level_arg(value: str) -> str:
    """Argparse type for supported log levels."""

    normalized = value.strip().upper()
    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if normalized not in valid_levels:
        raise argparse.ArgumentTypeError(
            f"value must be one of {', '.join(sorted(valid_levels))}"
        )
    return normalized


def bool_arg(value: str) -> bool:
    """Parse common boolean strings from environment variables."""

    normalized = value.strip().lower()
    truthy = {"1", "true", "yes", "on"}
    falsy = {"0", "false", "no", "off"}
    if normalized in truthy:
        return True
    if normalized in falsy:
        return False
    raise argparse.ArgumentTypeError("value must be a boolean-like string")


def price_sample_size_arg(value: str) -> int:
    """Argparse type for sample sizes supported by the v2 /top orderbook endpoint."""

    parsed = positive_int(value)
    if parsed > TOP_ORDER_SAMPLE_LIMIT:
        raise argparse.ArgumentTypeError(
            f"value must be between 1 and {TOP_ORDER_SAMPLE_LIMIT}"
        )
    return parsed


def env_var_name(name: str) -> str:
    """Build a namespaced environment variable name."""

    return f"{ENV_PREFIX}_{name}"


def read_env(name: str) -> str | None:
    """Read an environment variable, treating blank values as unset."""

    value = os.getenv(env_var_name(name))
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def resolve_option(
    cli_value: Any,
    env_name: str,
    default: Any,
    parser: Callable[[str], Any] | None = None,
) -> Any:
    """Resolve a setting from CLI input, environment, or fallback default."""

    if cli_value is not None:
        return cli_value

    raw_value = read_env(env_name)
    if raw_value is None:
        return default

    if parser is None:
        return raw_value

    try:
        return parser(raw_value)
    except argparse.ArgumentTypeError as exc:
        raise ValueError(f"{env_var_name(env_name)}: {exc}") from exc


def runtime_config_to_log_dict(settings: RuntimeConfig) -> dict[str, Any]:
    """Build a log-friendly view of the resolved runtime settings."""

    return {
        "api_v1_url": settings.api_v1_url,
        "api_v2_url": settings.api_v2_url,
        "platform": settings.platform,
        "language": settings.language,
        "crossplay": settings.crossplay,
        "requests_per_second": settings.requests_per_second,
        "request_timeout_seconds": settings.request_timeout_seconds,
        "max_retries": settings.max_retries,
        "output_dir": str(settings.output_dir),
        "output_prefix": settings.output_prefix,
        "output_file": str(settings.output_file) if settings.output_file else None,
        "log_level": settings.log_level,
        "log_file": str(settings.log_file) if settings.log_file else None,
        "profit_weight": settings.profit_weight,
        "volume_weight": settings.volume_weight,
        "price_sample_size": settings.price_sample_size,
        "allow_thin_orderbooks": settings.allow_thin_orderbooks,
        "json_summary": settings.json_summary,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Analyze Warframe Prime set profitability using v2 item/orderbook "
            "endpoints and the v1 statistics endpoint."
        )
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {APP_VERSION}")
    parser.add_argument("--profit-weight", type=non_negative_finite_float, default=None)
    parser.add_argument("--volume-weight", type=non_negative_finite_float, default=None)
    parser.add_argument(
        "--price-sample-size",
        type=price_sample_size_arg,
        default=None,
    )
    parser.add_argument("--requests-per-second", type=positive_float, default=None)
    parser.add_argument("--timeout", type=positive_float, default=None)
    parser.add_argument("--max-retries", type=positive_int, default=None)
    parser.add_argument("--platform", type=non_empty_string, default=None)
    parser.add_argument("--language", type=non_empty_string, default=None)
    parser.add_argument("--api-v1-url", type=non_empty_string, default=None)
    parser.add_argument("--api-v2-url", type=non_empty_string, default=None)
    parser.add_argument("--output-dir", type=non_empty_string, default=None)
    parser.add_argument("--output-prefix", type=non_empty_string, default=None)
    parser.add_argument("--output-file", type=non_empty_string, default=None)
    parser.add_argument("--log-level", type=log_level_arg, default=None)
    parser.add_argument("--log-file", type=non_empty_string, default=None)
    parser.add_argument("--debug", action="store_true", default=None)
    parser.add_argument(
        "--crossplay",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    parser.add_argument(
        "--allow-thin-orderbooks",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    parser.add_argument(
        "--json-summary",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    return parser.parse_args(argv)


def runtime_config_from_args(args: argparse.Namespace) -> RuntimeConfig:
    """Resolve runtime settings from CLI arguments and environment variables."""

    profit_weight = resolve_option(
        args.profit_weight,
        "PROFIT_WEIGHT",
        PROFIT_WEIGHT,
        non_negative_finite_float,
    )
    volume_weight = resolve_option(
        args.volume_weight,
        "VOLUME_WEIGHT",
        VOLUME_WEIGHT,
        non_negative_finite_float,
    )
    if profit_weight == 0 and volume_weight == 0:
        raise ValueError("At least one of profit_weight or volume_weight must be greater than zero")

    debug = resolve_option(args.debug, "DEBUG", DEBUG_MODE, bool_arg)
    log_level = resolve_option(args.log_level, "LOG_LEVEL", DEFAULT_LOG_LEVEL, log_level_arg)
    if debug:
        log_level = "DEBUG"

    output_file_value = resolve_option(args.output_file, "OUTPUT_FILE", None, non_empty_string)
    log_file_value = resolve_option(args.log_file, "LOG_FILE", DEFAULT_LOG_FILE, non_empty_string)

    return RuntimeConfig(
        api_v1_url=resolve_option(args.api_v1_url, "API_V1_URL", API_V1_URL, non_empty_string),
        api_v2_url=resolve_option(args.api_v2_url, "API_V2_URL", API_V2_URL, non_empty_string),
        platform=resolve_option(args.platform, "PLATFORM", DEFAULT_PLATFORM, non_empty_string),
        language=resolve_option(args.language, "LANGUAGE", DEFAULT_LANGUAGE, non_empty_string),
        crossplay=resolve_option(args.crossplay, "CROSSPLAY", DEFAULT_CROSSPLAY, bool_arg),
        requests_per_second=resolve_option(
            args.requests_per_second,
            "REQUESTS_PER_SECOND",
            REQUESTS_PER_SECOND,
            positive_float,
        ),
        request_timeout_seconds=resolve_option(
            args.timeout,
            "TIMEOUT",
            REQUEST_TIMEOUT_SECONDS,
            positive_float,
        ),
        max_retries=resolve_option(args.max_retries, "MAX_RETRIES", MAX_RETRIES, positive_int),
        output_dir=Path(resolve_option(args.output_dir, "OUTPUT_DIR", DEFAULT_OUTPUT_DIR, non_empty_string)),
        output_prefix=resolve_option(
            args.output_prefix,
            "OUTPUT_PREFIX",
            DEFAULT_OUTPUT_PREFIX,
            non_empty_string,
        ),
        output_file=Path(output_file_value) if output_file_value is not None else None,
        log_level=log_level,
        log_file=Path(log_file_value) if log_file_value is not None else None,
        debug=debug,
        json_summary=resolve_option(args.json_summary, "JSON_SUMMARY", JSON_SUMMARY, bool_arg),
        allow_thin_orderbooks=resolve_option(
            args.allow_thin_orderbooks,
            "ALLOW_THIN_ORDERBOOKS",
            ALLOW_THIN_ORDERBOOKS,
            bool_arg,
        ),
        profit_weight=profit_weight,
        volume_weight=volume_weight,
        price_sample_size=resolve_option(
            args.price_sample_size,
            "PRICE_SAMPLE_SIZE",
            PRICE_SAMPLE_SIZE,
            price_sample_size_arg,
        ),
    )


def build_summary(
    output_path: Path,
    report: AnalysisReport,
    settings: RuntimeConfig,
    duration_seconds: float,
) -> dict[str, Any]:
    """Build the run summary returned to operators."""

    return {
        "status": "ok",
        "run_id": settings.run_id,
        "completed_at": report.completed_at.isoformat(),
        "duration_seconds": round(duration_seconds, 3),
        "output_path": str(output_path),
        "catalog_set_count": report.catalog_set_count,
        "metadata_set_count": report.metadata_set_count,
        "ranked_set_count": len(report.results),
        "skipped_invalid_set_count": report.skipped_invalid_set_count,
        "skipped_missing_price_count": report.skipped_missing_price_count,
        "skipped_missing_volume_count": report.skipped_missing_volume_count,
        "price_sample_size": settings.price_sample_size,
        "allow_thin_orderbooks": settings.allow_thin_orderbooks,
    }


def render_human_summary(summary: dict[str, Any]) -> str:
    """Render a concise human-readable success summary."""

    return "\n".join(
        [
            f"Run {summary['run_id']} completed in {summary['duration_seconds']:.3f}s",
            (
                "Ranked {ranked_set_count} sets "
                "(catalog={catalog_set_count}, metadata={metadata_set_count}, "
                "skipped_invalid={skipped_invalid_set_count}, "
                "skipped_price={skipped_missing_price_count}, "
                "skipped_volume={skipped_missing_volume_count})"
            ).format(**summary),
            f"CSV written to: {summary['output_path']}",
        ]
    )


async def run_analysis(
    settings: RuntimeConfig,
    transport: Any = None,
) -> tuple[Path, AnalysisReport]:
    """Run analysis and persist the CSV output."""

    analyzer = SetProfitAnalyzer(settings, transport=transport)
    report = await analyzer.analyze()
    output_path = build_output_path(
        settings.output_dir,
        report.completed_at,
        prefix=settings.output_prefix,
        output_file=settings.output_file,
        run_id=None if settings.output_file is not None else settings.run_id,
    )
    write_results_to_csv(report.results, output_path)
    return output_path, report


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint."""

    args = parse_args(argv)

    try:
        settings = runtime_config_from_args(args)
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    configure_logging(settings)
    logger.info("%s %s starting", APP_NAME, APP_VERSION)
    logger.info(
        "Resolved runtime config: %s",
        json.dumps(runtime_config_to_log_dict(settings), sort_keys=True),
    )

    started_at = time.monotonic()
    try:
        output_path, report = asyncio.run(run_analysis(settings))
    except KeyboardInterrupt:
        logger.warning("Analysis interrupted by user")
        if settings.json_summary:
            print(json.dumps({"status": "interrupted", "run_id": settings.run_id}, sort_keys=True))
        return 130
    except Exception as exc:
        duration_seconds = time.monotonic() - started_at
        logger.error("Analyzer failed after %.3fs", duration_seconds, exc_info=True)
        if settings.json_summary:
            print(
                json.dumps(
                    {
                        "status": "failed",
                        "run_id": settings.run_id,
                        "duration_seconds": round(duration_seconds, 3),
                        "error": str(exc),
                        "log_file": str(settings.log_file) if settings.log_file else None,
                    },
                    sort_keys=True,
                )
            )
        else:
            print(f"Analysis failed: {exc}", file=sys.stderr)
            if settings.log_file:
                print(f"Check {settings.log_file} for details.", file=sys.stderr)
        return 1

    duration_seconds = time.monotonic() - started_at
    summary = build_summary(output_path, report, settings, duration_seconds)
    logger.info(
        "Analysis succeeded in %.3fs with %s ranked sets",
        duration_seconds,
        len(report.results),
    )

    if settings.json_summary:
        print(json.dumps(summary, sort_keys=True))
    else:
        print(render_human_summary(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
