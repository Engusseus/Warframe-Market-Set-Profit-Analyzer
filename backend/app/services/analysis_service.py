"""Analysis service for orchestrating market analysis.

This service coordinates the entire analysis workflow.
"""
import asyncio
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..config import get_settings
from ..core.cache_manager import CacheManager
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
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> AnalysisResponse:
        """Run complete market analysis.

        Args:
            profit_weight: Weight for profit scoring
            volume_weight: Weight for volume scoring
            force_refresh: Force fresh data fetch even if cache is valid
            progress_callback: Optional callback for progress updates

        Returns:
            AnalysisResponse with scored data
        """
        self._update_status("running", 0, "Starting analysis...")

        try:
            # Step 1: Fetch prime sets list
            self._update_status("running", 5, "Fetching Prime sets list...")
            prime_sets = await self.market_service.fetch_prime_sets()

            # Step 2: Check cache validity
            cache_valid = not force_refresh and self.cache_manager.is_cache_valid(prime_sets)

            if cache_valid:
                self._update_status("running", 10, "Using cached data...")
                detailed_sets = self.cache_manager.get_detailed_sets()
            else:
                # Slow path: fetch all set details
                self._update_status("running", 10, "Fetching set details (this may take a few minutes)...")

                def detail_progress(current, total, msg):
                    pct = 10 + int((current / total) * 30)
                    self._update_status("running", pct, msg)

                detailed_sets = await self.market_service.fetch_complete_set_data(
                    prime_sets,
                    progress_callback=detail_progress
                )

                # Update cache
                self.cache_manager.update_cache(prime_sets, detailed_sets)

            if not detailed_sets:
                raise Exception("No detailed sets available")

            # Step 3: Fetch current pricing data
            self._update_status("running", 40, "Fetching set prices...")

            def set_price_progress(current, total, msg):
                pct = 40 + int((current / total) * 15)
                self._update_status("running", pct, msg)

            set_prices = await self.market_service.fetch_set_lowest_prices(
                detailed_sets,
                progress_callback=set_price_progress
            )

            # Step 4: Fetch part prices
            self._update_status("running", 55, "Fetching part prices...")

            def part_price_progress(current, total, msg):
                pct = 55 + int((current / total) * 20)
                self._update_status("running", pct, msg)

            part_prices = await self.market_service.fetch_part_lowest_prices(
                detailed_sets,
                progress_callback=part_price_progress
            )

            # Step 5: Fetch volume data
            self._update_status("running", 75, "Fetching volume data...")

            def volume_progress(current, total, msg):
                pct = 75 + int((current / total) * 15)
                self._update_status("running", pct, msg)

            volume_data = await self.market_service.fetch_set_volume(
                detailed_sets,
                progress_callback=volume_progress
            )

            # Step 6: Calculate profit margins
            self._update_status("running", 90, "Calculating profits...")
            profit_data = calculate_profit_margins_dict(
                set_prices, part_prices, detailed_sets
            )

            if not profit_data:
                raise Exception("No profitable sets found")

            # Step 7: Calculate scores
            self._update_status("running", 95, "Calculating scores...")
            scored_data = calculate_profitability_scores_dict(
                profit_data, volume_data, profit_weight, volume_weight
            )

            # Store current data for rescoring
            self._current_data = scored_data
            self._current_weights = (profit_weight, volume_weight)

            # Step 8: Save to database
            run_id = None
            try:
                db = await self.get_database()
                run_id = await db.save_market_run(profit_data, set_prices)
                self.status.run_id = run_id
            except Exception as e:
                # Don't fail analysis if DB save fails
                pass

            # Convert to response
            self._update_status("completed", 100, "Analysis complete!")

            # Convert dict data to ScoredData models
            scored_models = [ScoredData(**item) for item in scored_data]

            return AnalysisResponse(
                run_id=run_id,
                timestamp=datetime.now(),
                sets=scored_models,
                total_sets=len(scored_models),
                profitable_sets=len([s for s in scored_models if s.profit_margin > 0]),
                weights=WeightsConfig(
                    profit_weight=profit_weight,
                    volume_weight=volume_weight
                ),
                cached=cache_valid
            )

        except Exception as e:
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
