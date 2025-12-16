"""Analysis service for orchestrating market analysis.

This service coordinates the entire analysis workflow.
"""
import asyncio
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..config import get_settings
from ..core.cache_manager import CacheManager
from ..core.logging import get_logger
from ..core.profit_calculator import calculate_profit_margins_dict
from ..core.scoring import calculate_profitability_scores_dict, recalculate_scores_with_new_weights
from ..db.database import AsyncMarketDatabase
from ..models.schemas import (
    AnalysisResponse,
    ScoredData,
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

    async def get_database(self) -> AsyncMarketDatabase:
        """Get or create database instance."""
        if self.database is None:
            self.database = AsyncMarketDatabase()
        return self.database

    def _update_status(
        self,
        status: str,
        progress: int = 0,
        message: str = ""
    ) -> None:
        """Update analysis status."""
        self.status.status = status
        self.status.progress = progress
        self.status.message = message

    async def run_full_analysis(
        self,
        profit_weight: float = 1.0,
        volume_weight: float = 1.2,
        force_refresh: bool = False,
        test_mode: bool = False,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> AnalysisResponse:
        """Run complete market analysis.

        Args:
            profit_weight: Weight for profit scoring
            volume_weight: Weight for volume scoring
            force_refresh: Force fresh data fetch even if cache is valid
            test_mode: If True, only fetch a small subset of data for testing
            progress_callback: Optional callback for progress updates

        Returns:
            AnalysisResponse with scored data
        """
        logger = get_logger()
        logger.info("=" * 50)
        logger.info("Starting full analysis")
        logger.info(f"Parameters: profit_weight={profit_weight}, volume_weight={volume_weight}, force_refresh={force_refresh}, test_mode={test_mode}")
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
            self._update_status("running", 90, "Calculating profits...")
            profit_data = calculate_profit_margins_dict(
                set_prices, part_prices, detailed_sets
            )

            if not profit_data:
                logger.error("No profitable sets found after calculation")
                raise Exception("No profitable sets found")
            logger.info(f"Calculated profit margins for {len(profit_data)} sets")

            # Step 7: Calculate scores
            logger.info("Step 7: Calculating scores...")
            self._update_status("running", 95, "Calculating scores...")
            scored_data = calculate_profitability_scores_dict(
                profit_data, volume_data, profit_weight, volume_weight
            )
            logger.info(f"Calculated scores for {len(scored_data)} sets")

            # Store current data for rescoring
            self._current_data = scored_data
            self._current_weights = (profit_weight, volume_weight)

            # Step 8: Save to database
            logger.info("Step 8: Saving to database...")
            run_id = None
            try:
                db = await self.get_database()
                run_id = await db.save_market_run(profit_data, set_prices)
                self.status.run_id = run_id
                logger.info(f"Saved analysis run to database with ID: {run_id}")
            except Exception as e:
                # Don't fail analysis if DB save fails
                logger.warning(f"Failed to save to database: {e}")

            # Convert to response
            self._update_status("completed", 100, "Analysis complete!")

            # Convert dict data to ScoredData models
            scored_models = [ScoredData(**item) for item in scored_data]

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
                    profit_weight=profit_weight,
                    volume_weight=volume_weight
                ),
                cached=cache_valid
            )

        except Exception as e:
            logger.error(f"Analysis failed with error: {e}", exc_info=True)
            self.status.status = "error"
            self.status.error = str(e)
            raise

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

            run_data = await db.get_run_by_id(latest_run_id)
            if not run_data:
                return None

            # Convert to response format
            sets_data = run_data.get('set_profits', [])
            scored_sets = []
            for s in sets_data:
                scored_sets.append(ScoredData(
                    set_slug=s.get('set_slug', ''),
                    set_name=s.get('set_name', ''),
                    set_price=s.get('lowest_price', 0),
                    part_cost=0,  # Not stored in DB
                    profit_margin=s.get('profit_margin', 0),
                    profit_percentage=0,  # Not stored in DB
                    part_details=[],
                    volume=0,
                    normalized_profit=0,
                    normalized_volume=0,
                    profit_score=0,
                    volume_score=0,
                    total_score=0
                ))

            return AnalysisResponse(
                run_id=latest_run_id,
                timestamp=datetime.fromisoformat(run_data.get('date_string', '')),
                sets=scored_sets,
                total_sets=len(scored_sets),
                profitable_sets=len([s for s in scored_sets if s.profit_margin > 0]),
                weights=WeightsConfig(),
                cached=True
            )
        except Exception:
            return None

    async def recalculate_scores(
        self,
        profit_weight: float,
        volume_weight: float
    ) -> Optional[List[Dict[str, Any]]]:
        """Recalculate scores with new weights using current data.

        Args:
            profit_weight: New profit weight
            volume_weight: New volume weight

        Returns:
            Rescored data list or None if no current data
        """
        if self._current_data is None:
            return None

        new_weights = (profit_weight, volume_weight)
        old_weights = self._current_weights or (1.0, 1.2)

        rescored = recalculate_scores_with_new_weights(
            self._current_data,
            new_weights,
            old_weights
        )

        self._current_data = rescored
        self._current_weights = new_weights

        return rescored

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
        await self.market_service.close()
        if self.database:
            await self.database.close()
