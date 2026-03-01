"""Analysis service for orchestrating market analysis.

This service coordinates the entire analysis workflow with the multiplicative
scoring model and strategy profiles.
"""
import asyncio
from contextlib import suppress
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..config import get_settings
from ..core.cache_manager import CacheManager
from ..core.logging import get_logger
from ..core.profit_calculator import calculate_profit_margins_dict
from ..core.scoring import (
    calculate_profitability_scores_dict,
    calculate_profitability_scores_with_metrics,
    recalculate_scores_with_new_weights,
    recalculate_scores_with_strategy,
)
from ..core.statistics import calculate_metrics_from_history
from ..core.strategy_profiles import StrategyType, get_all_strategies
from ..db.database import AsyncMarketDatabase
from ..models.schemas import (
    AnalysisResponse,
    ExecutionMode,
    ScoredData,
    StrategyType as SchemaStrategyType,
    WeightsConfig,
)
from .warframe_market import WarframeMarketService


class AnalysisStatus:
    """Track analysis status for async operations."""

    def __init__(self):
        self.status: str = "idle"  # idle, running, completed, error
        self.progress: int = 0
        self.message: str = ""
        self.run_id: Optional[int] = None
        self.error: Optional[str] = None


class AnalysisService:
    """Service for orchestrating market analysis."""

    def __init__(
        self,
        market_service: Optional[WarframeMarketService] = None,
        cache_manager: Optional[CacheManager] = None,
        database: Optional[AsyncMarketDatabase] = None
    ):
        """Initialize the analysis service.

        Args:
            market_service: Warframe Market API service
            cache_manager: Cache manager instance
            database: Database instance
        """
        settings = get_settings()
        self.market_service = market_service or WarframeMarketService()
        self.cache_manager = cache_manager or CacheManager(settings.cache_dir)
        self.database = database
        self.status = AnalysisStatus()
        self._current_data: Optional[List[Dict[str, Any]]] = None
        self._current_weights: Optional[Tuple[float, float]] = None
        self._current_strategy: StrategyType = StrategyType.BALANCED
        self._current_execution_mode: ExecutionMode = ExecutionMode.INSTANT
        self._analysis_lock = asyncio.Lock()
        self._status_event = asyncio.Event()
        self._polling_stop_event = asyncio.Event()
        self._polling_task: Optional[asyncio.Task[None]] = None
        self._poll_interval_seconds = max(30.0, float(settings.analysis_timeout) / 2.0)
        self._status_event.set()

    async def get_database(self) -> AsyncMarketDatabase:
        """Get or create database instance."""
        if self.database is None:
            self.database = AsyncMarketDatabase()
        return self.database

    def _update_status(
        self,
        status: str,
        progress: int = 0,
        message: str = "",
        error: Optional[str] = None
    ) -> None:
        """Update analysis status."""
        self.status.status = status
        self.status.progress = progress
        self.status.message = message
        if status == "error":
            self.status.error = error
        elif error is not None:
            self.status.error = error
        else:
            self.status.error = None
        self._status_event.set()

    async def wait_for_status_update(self, timeout: float = 1.0) -> bool:
        """Wait for a status update event.

        Args:
            timeout: Max seconds to wait.

        Returns:
            True when an update was received, False on timeout.
        """
        try:
            await asyncio.wait_for(self._status_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            return False
        self._status_event.clear()
        return True

    async def _continuous_polling_loop(
        self,
        poll_interval_seconds: float,
        force_refresh: bool
    ) -> None:
        """Run analysis continuously in the background."""
        logger = get_logger()
        logger.info(
            "Starting continuous polling loop (interval=%ss, force_refresh=%s)",
            poll_interval_seconds,
            force_refresh,
        )
        try:
            while not self._polling_stop_event.is_set():
                if self._analysis_lock.locked():
                    logger.info("Skipping polling cycle because analysis is already running")
                else:
                    try:
                        await self.run_full_analysis(
                            strategy=self._current_strategy,
                            execution_mode=self._current_execution_mode,
                            force_refresh=force_refresh,
                            test_mode=False,
                        )
                    except Exception as e:
                        logger.warning(f"Background polling analysis failed: {e}")

                try:
                    await asyncio.wait_for(
                        self._polling_stop_event.wait(),
                        timeout=poll_interval_seconds,
                    )
                except asyncio.TimeoutError:
                    continue
        except asyncio.CancelledError:
            logger.info("Continuous polling loop cancelled")
            raise
        finally:
            logger.info("Continuous polling loop stopped")

    async def start_continuous_polling(
        self,
        poll_interval_seconds: Optional[float] = None,
        force_refresh: bool = False
    ) -> None:
        """Start continuous background polling if not already running."""
        if self._polling_task is not None and not self._polling_task.done():
            return

        interval = poll_interval_seconds or self._poll_interval_seconds
        if interval <= 0:
            raise ValueError("poll_interval_seconds must be positive")

        self._polling_stop_event.clear()
        self._polling_task = asyncio.create_task(
            self._continuous_polling_loop(interval, force_refresh)
        )

    async def stop_continuous_polling(self) -> None:
        """Stop continuous background polling."""
        self._polling_stop_event.set()
        if self._polling_task is None:
            return

        self._polling_task.cancel()
        with suppress(asyncio.CancelledError):
            await self._polling_task
        self._polling_task = None

    async def run_full_analysis(
        self,
        strategy: StrategyType = StrategyType.BALANCED,
        execution_mode: ExecutionMode = ExecutionMode.INSTANT,
        force_refresh: bool = False,
        test_mode: bool = False,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        # Legacy parameters for backward compatibility
        profit_weight: float = 1.0,
        volume_weight: float = 1.2,
    ) -> AnalysisResponse:
        """Run complete market analysis with strategy-based scoring.

        Args:
            strategy: Trading strategy to use for scoring
            execution_mode: Whether to score instant or patient execution assumptions
            force_refresh: Force fresh data fetch even if cache is valid
            test_mode: If True, only fetch a small subset of data for testing
            progress_callback: Optional callback for progress updates
            profit_weight: Legacy weight parameter (ignored, kept for compatibility)
            volume_weight: Legacy weight parameter (ignored, kept for compatibility)

        Returns:
            AnalysisResponse with scored data
        """
        logger = get_logger()
        logger.info("=" * 50)
        logger.info("Starting full analysis")
        logger.info(
            "Parameters: strategy=%s, execution_mode=%s, force_refresh=%s, test_mode=%s",
            strategy.value,
            execution_mode.value,
            force_refresh,
            test_mode,
        )
        await self._analysis_lock.acquire()
        self._update_status("running", 0, "Starting analysis...")

        try:
            # Step 1: Fetch prime sets list
            logger.info("Step 1: Fetching Prime sets list from Warframe Market API...")
            self._update_status("running", 5, "Fetching Prime sets list...")

            limit = 10 if test_mode else None
            prime_sets = await self.market_service.fetch_prime_sets(limit=limit)
            logger.info(f"Found {len(prime_sets)} Prime sets")

            # Step 2: Check cache validity (SHA-256 hash check)
            logger.info("Step 2: Checking cache validity (SHA-256 hash)...")
            cache_valid = not force_refresh and self.cache_manager.is_cache_valid(prime_sets)
            logger.debug(f"SHA-256 cache valid: {cache_valid}")

            # Step 2b: Canary check - validate random set against API
            if cache_valid:
                logger.info("Step 2b: Performing canary validation...")
                self._update_status("running", 7, "Validating cache integrity...")

                canary_slug = self.cache_manager.get_random_set_for_canary()
                if canary_slug:
                    logger.info(f"Canary check: validating {canary_slug}")
                    cached_set = self.cache_manager.get_cached_set_by_slug(canary_slug)
                    fresh_set = await self.market_service.fetch_single_set_for_canary(canary_slug)

                    if cached_set and fresh_set:
                        is_valid, reason = self.cache_manager.compare_set_data(cached_set, fresh_set)
                        if is_valid:
                            logger.info(f"Canary check passed for {canary_slug}")
                        else:
                            logger.warning(f"Canary check FAILED for {canary_slug}: {reason}")
                            logger.warning("Cache appears stale - forcing full refresh")
                            cache_valid = False
                    elif fresh_set is None:
                        # API fetch failed - trust the cache rather than failing
                        logger.warning(f"Canary check: could not fetch {canary_slug} from API, trusting cache")
                    else:
                        # Cached set not found - something wrong with cache
                        logger.warning(f"Canary check: {canary_slug} not found in cache, forcing refresh")
                        cache_valid = False
                else:
                    logger.warning("Canary check: no sets in cache to validate")
                    cache_valid = False

            if cache_valid:
                logger.info("Using cached set details")
                self._update_status("running", 10, "Using cached data...")
                detailed_sets = self.cache_manager.get_detailed_sets()
                logger.info(f"Loaded {len(detailed_sets)} sets from cache")
            else:
                # Slow path: fetch all set details
                logger.info("Cache invalid or force refresh - fetching all set details (this may take several minutes)...")
                self._update_status("running", 10, "Fetching set details (this may take a few minutes)...")

                def detail_progress(current, total, msg):
                    pct = 10 + int((current / total) * 30)
                    self._update_status("running", pct, msg)
                    if current % 20 == 0 or current == total:
                        logger.debug(f"Set details progress: {current}/{total}")

                detailed_sets = await self.market_service.fetch_complete_set_data(
                    prime_sets,
                    progress_callback=detail_progress
                )
                logger.info(f"Fetched details for {len(detailed_sets)} sets")

                # Update cache
                logger.debug("Updating cache with new data")
                self.cache_manager.update_cache(prime_sets, detailed_sets)

            if not detailed_sets:
                logger.error("No detailed sets available")
                raise Exception("No detailed sets available")

            # Step 3: Fetch current pricing data
            logger.info("Step 3: Fetching set prices...")
            self._update_status("running", 40, "Fetching set prices...")

            def set_price_progress(current, total, msg):
                pct = 40 + int((current / total) * 15)
                self._update_status("running", pct, msg)
                if current % 50 == 0 or current == total:
                    logger.debug(f"Set prices progress: {current}/{total}")

            set_prices = await self.market_service.fetch_set_lowest_prices(
                detailed_sets,
                progress_callback=set_price_progress
            )
            logger.info(f"Fetched prices for {len(set_prices)} sets")

            # Step 4: Fetch part prices
            logger.info("Step 4: Fetching part prices...")
            self._update_status("running", 55, "Fetching part prices...")

            def part_price_progress(current, total, msg):
                pct = 55 + int((current / total) * 20)
                self._update_status("running", pct, msg)
                if current % 100 == 0 or current == total:
                    logger.debug(f"Part prices progress: {current}/{total}")

            part_prices = await self.market_service.fetch_part_lowest_prices(
                detailed_sets,
                progress_callback=part_price_progress
            )
            logger.info(f"Fetched prices for {len(part_prices)} parts")

            # Step 5: Fetch volume data
            logger.info("Step 5: Fetching volume data...")
            self._update_status("running", 75, "Fetching volume data...")

            def volume_progress(current, total, msg):
                pct = 75 + int((current / total) * 15)
                self._update_status("running", pct, msg)
                if current % 50 == 0 or current == total:
                    logger.debug(f"Volume data progress: {current}/{total}")

            volume_data = await self.market_service.fetch_set_volume(
                detailed_sets,
                progress_callback=volume_progress
            )
            logger.info(f"Fetched volume data, total volume: {volume_data.get('total', 0)}")

            # Step 6: Calculate profit margins
            logger.info("Step 6: Calculating profit margins...")
            self._update_status("running", 80, "Calculating profits...")
            profit_data = calculate_profit_margins_dict(
                set_prices, part_prices, detailed_sets
            )

            if not profit_data:
                logger.error("No profitable sets found after calculation")
                raise Exception("No profitable sets found")
            logger.info(f"Calculated profit margins for {len(profit_data)} sets")

            # Step 7: Calculate trend and volatility metrics from historical data
            logger.info("Step 7: Calculating trend and volatility metrics...")
            self._update_status("running", 85, "Analyzing price trends...")

            db = await self.get_database()
            set_slugs = [item['set_slug'] for item in profit_data]

            # Batch fetch 7-day price history for all sets
            historical_data = await db.get_price_history_batch(set_slugs, days=7)

            # Calculate metrics for each set
            trend_volatility_metrics: Dict[str, Dict[str, Any]] = {}
            for set_slug in set_slugs:
                history = historical_data.get(set_slug, [])
                metrics = calculate_metrics_from_history(history)
                trend_volatility_metrics[set_slug] = metrics

            logger.info(f"Calculated trend/volatility metrics for {len(trend_volatility_metrics)} sets")

            # Step 8: Calculate composite scores with strategy
            logger.info(f"Step 8: Calculating composite scores with {strategy.value} strategy...")
            self._update_status("running", 92, f"Applying {strategy.value} strategy...")

            scored_models = calculate_profitability_scores_with_metrics(
                profit_data,
                volume_data,
                trend_volatility_metrics,
                strategy=strategy,
                execution_mode=execution_mode
            )

            # Convert to dict format for storage and rescoring
            scored_data = [s.model_dump() for s in scored_models]
            logger.info(f"Calculated composite scores for {len(scored_data)} sets")

            # Store current data for rescoring
            self._current_data = scored_data
            self._current_weights = (1.0, 1.2)  # Legacy
            self._current_strategy = strategy
            self._current_execution_mode = execution_mode

            # Step 9: Save to database
            logger.info("Step 9: Saving to database...")
            self._update_status("running", 96, "Saving results...")
            run_id = None
            try:
                run_id = await db.save_market_run(profit_data, set_prices)
                self.status.run_id = run_id
                logger.info(f"Saved analysis run to database with ID: {run_id}")

                # Save full scored data for historical restoration
                await db.save_full_analysis(
                    run_id,
                    scored_data,
                    profit_weight=1.0,
                    volume_weight=1.2,
                    strategy=strategy.value,
                    execution_mode=execution_mode.value,
                )
                logger.info(f"Saved full analysis data for run {run_id}")
            except Exception as e:
                # Don't fail analysis if DB save fails
                logger.warning(f"Failed to save to database: {e}")

            # Convert to response
            self._update_status("completed", 100, "Analysis complete!")

            profitable_count = len([s for s in scored_models if s.profit_margin > 0])
            logger.info("=" * 50)
            logger.info(f"Analysis complete! Total sets: {len(scored_models)}, Profitable: {profitable_count}")
            logger.info("=" * 50)

            return AnalysisResponse(
                run_id=run_id,
                timestamp=datetime.now(),
                sets=scored_models,
                total_sets=len(scored_models),
                profitable_sets=profitable_count,
                weights=WeightsConfig(
                    strategy=SchemaStrategyType(strategy.value),
                    profit_weight=1.0,
                    volume_weight=1.2
                ),
                strategy=SchemaStrategyType(strategy.value),
                execution_mode=execution_mode,
                cached=cache_valid
            )

        except asyncio.CancelledError:
            self._update_status(
                "idle",
                self.status.progress,
                "Analysis cancelled",
            )
            raise
        except Exception as e:
            logger.error(f"Analysis failed with error: {e}", exc_info=True)
            self._update_status(
                "error",
                self.status.progress,
                self.status.message or "Analysis failed",
                error=str(e),
            )
            raise
        finally:
            self._analysis_lock.release()

    async def get_latest_analysis(self) -> Optional[AnalysisResponse]:
        """Get the most recent analysis from database.

        Returns:
            AnalysisResponse or None if no data
        """
        try:
            db = await self.get_database()
            latest_run_id = await db.get_latest_run_id()

            if latest_run_id is None:
                return None

            full_analysis = await db.get_full_analysis(latest_run_id)
            if full_analysis:
                raw_execution_mode = full_analysis.get("execution_mode", "instant")
                try:
                    run_execution_mode = ExecutionMode(str(raw_execution_mode).strip().lower())
                except ValueError:
                    run_execution_mode = ExecutionMode.INSTANT

                scored_sets: List[ScoredData] = []
                for row in full_analysis.get("sets", []):
                    row_execution_mode = row.get("execution_mode", run_execution_mode.value)
                    try:
                        parsed_row_mode = ExecutionMode(str(row_execution_mode).strip().lower())
                    except ValueError:
                        parsed_row_mode = run_execution_mode

                    scored_sets.append(
                        ScoredData(
                            set_slug=row.get("set_slug", ""),
                            set_name=row.get("set_name", ""),
                            set_price=row.get("set_price", 0.0),
                            part_cost=row.get("part_cost", 0.0),
                            profit_margin=row.get("profit_margin", 0.0),
                            profit_percentage=row.get("profit_percentage", 0.0),
                            instant_set_price=row.get("instant_set_price"),
                            instant_part_cost=row.get("instant_part_cost"),
                            instant_profit_margin=row.get("instant_profit_margin"),
                            instant_profit_percentage=row.get("instant_profit_percentage"),
                            patient_set_price=row.get("patient_set_price"),
                            patient_part_cost=row.get("patient_part_cost"),
                            patient_profit_margin=row.get("patient_profit_margin"),
                            patient_profit_percentage=row.get("patient_profit_percentage"),
                            part_details=row.get("part_details", []),
                            execution_mode=parsed_row_mode,
                            volume=row.get("volume", 0),
                            normalized_profit=row.get("normalized_profit", 0.0),
                            normalized_volume=row.get("normalized_volume", 0.0),
                            profit_score=row.get("profit_score", 0.0),
                            volume_score=row.get("volume_score", 0.0),
                            total_score=row.get("total_score", 0.0),
                            trend_slope=row.get("trend_slope", 0.0),
                            trend_multiplier=row.get("trend_multiplier", 1.0),
                            trend_direction=row.get("trend_direction", "stable"),
                            volatility=row.get("volatility", 0.0),
                            volatility_penalty=row.get("volatility_penalty", 1.0),
                            risk_level=row.get("risk_level", "Medium"),
                            composite_score=row.get("composite_score", row.get("total_score", 0.0)),
                            profit_contribution=row.get("profit_contribution", 0.0),
                            volume_contribution=row.get("volume_contribution", 0.0),
                            trend_contribution=row.get("trend_contribution", 1.0),
                            volatility_contribution=row.get("volatility_contribution", 1.0),
                            bid_ask_ratio=row.get("bid_ask_ratio", 0.0),
                            sell_side_competition=row.get("sell_side_competition", 0.0),
                            liquidity_velocity=row.get("liquidity_velocity", 0.0),
                            liquidity_multiplier=row.get("liquidity_multiplier", 1.0),
                        )
                    )

                timestamp = datetime.fromtimestamp(full_analysis.get("timestamp", 0))
                date_string = full_analysis.get("date_string")
                if date_string:
                    try:
                        timestamp = datetime.strptime(date_string, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        pass

                weights_data = full_analysis.get("weights", {})
                strategy_value = str(full_analysis.get("strategy", "balanced"))
                try:
                    strategy = SchemaStrategyType(strategy_value)
                except ValueError:
                    strategy = SchemaStrategyType.BALANCED

                return AnalysisResponse(
                    run_id=full_analysis["run_id"],
                    timestamp=timestamp,
                    sets=scored_sets,
                    total_sets=full_analysis.get("total_sets", len(scored_sets)),
                    profitable_sets=full_analysis.get(
                        "profitable_sets",
                        len([s for s in scored_sets if s.profit_margin > 0]),
                    ),
                    weights=WeightsConfig(
                        profit_weight=weights_data.get("profit_weight", 1.0),
                        volume_weight=weights_data.get("volume_weight", 1.2),
                        strategy=weights_data.get("strategy", strategy),
                    ),
                    strategy=strategy,
                    execution_mode=run_execution_mode,
                    cached=True,
                )

            run_data = await db.get_run_by_id(latest_run_id)
            if not run_data:
                return None

            scored_sets = [
                ScoredData(
                    set_slug=s.get("set_slug", ""),
                    set_name=s.get("set_name", ""),
                    set_price=s.get("lowest_price", 0),
                    part_cost=0,
                    profit_margin=s.get("profit_margin", 0),
                    profit_percentage=0,
                    part_details=[],
                    volume=0,
                    normalized_profit=0,
                    normalized_volume=0,
                    profit_score=0,
                    volume_score=0,
                    total_score=0,
                )
                for s in run_data.get("set_profits", [])
            ]

            timestamp = datetime.fromtimestamp(run_data.get("timestamp", 0))
            date_string = run_data.get("date_string")
            if date_string:
                try:
                    timestamp = datetime.strptime(date_string, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    pass

            return AnalysisResponse(
                run_id=latest_run_id,
                timestamp=timestamp,
                sets=scored_sets,
                total_sets=len(scored_sets),
                profitable_sets=len([s for s in scored_sets if s.profit_margin > 0]),
                weights=WeightsConfig(),
                execution_mode=ExecutionMode.INSTANT,
                cached=True,
            )
        except Exception:
            return None

    async def recalculate_scores(
        self,
        strategy: StrategyType = StrategyType.BALANCED,
        execution_mode: Optional[ExecutionMode] = None,
        # Legacy parameters
        profit_weight: float = 1.0,
        volume_weight: float = 1.2
    ) -> Optional[List[Dict[str, Any]]]:
        """Recalculate scores with a new strategy using current data.

        Args:
            strategy: New strategy to apply
            execution_mode: Optional execution mode override
            profit_weight: Legacy parameter (ignored)
            volume_weight: Legacy parameter (ignored)

        Returns:
            Rescored data list or None if no current data
        """
        if self._current_data is None:
            return None

        selected_mode = execution_mode or self._current_execution_mode

        rescored = recalculate_scores_with_strategy(
            self._current_data,
            strategy,
            execution_mode=selected_mode
        )

        self._current_data = rescored
        self._current_strategy = strategy
        self._current_execution_mode = selected_mode

        return rescored

    def get_available_strategies(self) -> List[Dict[str, Any]]:
        """Get all available trading strategies.

        Returns:
            List of strategy profile dictionaries
        """
        return get_all_strategies()

    def get_status(self) -> Dict[str, Any]:
        """Get current analysis status.

        Returns:
            Status dictionary
        """
        return {
            "status": self.status.status,
            "progress": self.status.progress,
            "message": self.status.message,
            "run_id": self.status.run_id,
            "error": self.status.error
        }

    async def close(self) -> None:
        """Clean up resources."""
        await self.stop_continuous_polling()
        await self.market_service.close()
        if self.database:
            await self.database.close()
