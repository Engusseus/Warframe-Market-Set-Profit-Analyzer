"""Unit tests for scoring algorithms."""
import pytest

from app.core.scoring import (
    calculate_composite_score,
    calculate_profitability_scores_with_metrics,
    calculate_profitability_scores,
    recalculate_scores_with_strategy,
)
from app.core.strategy_profiles import StrategyType
from app.models.schemas import ExecutionMode


class TestCalculateCompositeScore:
    """Tests for calculate_composite_score function."""

    @pytest.mark.unit
    def test_basic_calculation(self):
        """Test basic score calculation with typical values."""
        score = calculate_composite_score(
            profit=50.0,
            volume=100,
            roi=50.0,
            trend_multiplier=1.0,
            volatility_penalty=1.0,
        )
        # Expected: (50 * log10(100)) * (1 + 50/100) * 1.0 / 1.0
        # = (50 * 2) * 1.5 = 150
        assert score == pytest.approx(150.0)

    @pytest.mark.unit
    def test_zero_volume_handled(self):
        """Test that zero volume doesn't cause errors."""
        score = calculate_composite_score(
            profit=50.0,
            volume=0,
            roi=50.0,
            trend_multiplier=1.0,
            volatility_penalty=1.0,
        )
        # Should use minimum volume factor of 0.1
        # Expected: (50 * 0.1) * 1.5 = 7.5
        assert score == pytest.approx(7.5)

    @pytest.mark.unit
    def test_volume_one_uses_minimum_factor(self):
        """Test that volume of 1 uses minimum factor."""
        score = calculate_composite_score(
            profit=50.0,
            volume=1,
            roi=50.0,
            trend_multiplier=1.0,
            volatility_penalty=1.0,
        )
        # log10(1) = 0, so min factor of 0.1 is used
        # Expected: (50 * 0.1) * 1.5 = 7.5
        assert score == pytest.approx(7.5)

    @pytest.mark.unit
    def test_negative_profit_returns_negative_score(self):
        """Test that unprofitable items get negative scores."""
        score = calculate_composite_score(
            profit=-20.0,
            volume=100,
            roi=-10.0,
            trend_multiplier=1.0,
            volatility_penalty=1.0,
        )
        assert score < 0

    @pytest.mark.unit
    def test_negative_base_with_negative_roi_becomes_more_negative(self):
        """Test sign-preserving ROI scaling for negative base scores."""
        score_without_roi = calculate_composite_score(
            profit=-20.0,
            volume=100,
            roi=0.0,
            trend_multiplier=1.0,
            volatility_penalty=1.0,
        )
        score_with_negative_roi = calculate_composite_score(
            profit=-20.0,
            volume=100,
            roi=-50.0,
            trend_multiplier=1.0,
            volatility_penalty=1.0,
        )

        assert score_with_negative_roi < score_without_roi
        assert abs(score_with_negative_roi) > abs(score_without_roi)
        assert score_with_negative_roi == pytest.approx(-60.0)

    @pytest.mark.unit
    def test_negative_base_with_positive_roi_is_dampened(self):
        """Test that opposing ROI direction reduces negative magnitude."""
        score_without_roi = calculate_composite_score(
            profit=-20.0,
            volume=100,
            roi=0.0,
            trend_multiplier=1.0,
            volatility_penalty=1.0,
        )
        score_with_positive_roi = calculate_composite_score(
            profit=-20.0,
            volume=100,
            roi=50.0,
            trend_multiplier=1.0,
            volatility_penalty=1.0,
        )

        assert abs(score_with_positive_roi) < abs(score_without_roi)
        assert score_with_positive_roi == pytest.approx(-20.0)

    @pytest.mark.unit
    def test_high_volatility_penalty_reduces_score(self):
        """Test that volatility penalty reduces the score."""
        score_low_vol = calculate_composite_score(
            profit=50.0, volume=100, roi=50.0,
            trend_multiplier=1.0, volatility_penalty=1.0
        )
        score_high_vol = calculate_composite_score(
            profit=50.0, volume=100, roi=50.0,
            trend_multiplier=1.0, volatility_penalty=2.0
        )
        assert score_high_vol < score_low_vol
        assert score_high_vol == pytest.approx(score_low_vol / 2)

    @pytest.mark.unit
    def test_rising_trend_increases_score(self):
        """Test that rising trend (multiplier > 1) increases score."""
        score_stable = calculate_composite_score(
            profit=50.0, volume=100, roi=50.0,
            trend_multiplier=1.0, volatility_penalty=1.0
        )
        score_rising = calculate_composite_score(
            profit=50.0, volume=100, roi=50.0,
            trend_multiplier=1.5, volatility_penalty=1.0
        )
        assert score_rising > score_stable
        assert score_rising == pytest.approx(score_stable * 1.5)

    @pytest.mark.unit
    def test_falling_trend_decreases_score(self):
        """Test that falling trend (multiplier < 1) decreases score."""
        score_stable = calculate_composite_score(
            profit=50.0, volume=100, roi=50.0,
            trend_multiplier=1.0, volatility_penalty=1.0
        )
        score_falling = calculate_composite_score(
            profit=50.0, volume=100, roi=50.0,
            trend_multiplier=0.5, volatility_penalty=1.0
        )
        assert score_falling < score_stable
        assert score_falling == pytest.approx(score_stable * 0.5)

    @pytest.mark.unit
    def test_high_roi_increases_score(self):
        """Test that higher ROI increases score."""
        score_low_roi = calculate_composite_score(
            profit=50.0, volume=100, roi=10.0,
            trend_multiplier=1.0, volatility_penalty=1.0
        )
        score_high_roi = calculate_composite_score(
            profit=50.0, volume=100, roi=100.0,
            trend_multiplier=1.0, volatility_penalty=1.0
        )
        assert score_high_roi > score_low_roi

    @pytest.mark.unit
    def test_high_volume_increases_score(self):
        """Test that higher volume increases score logarithmically."""
        score_low_vol = calculate_composite_score(
            profit=50.0, volume=10, roi=50.0,
            trend_multiplier=1.0, volatility_penalty=1.0
        )
        score_high_vol = calculate_composite_score(
            profit=50.0, volume=1000, roi=50.0,
            trend_multiplier=1.0, volatility_penalty=1.0
        )
        assert score_high_vol > score_low_vol
        # Volume 1000 has log10=3, volume 10 has log10=1, so ratio should be 3
        assert score_high_vol / score_low_vol == pytest.approx(3.0)

    @pytest.mark.unit
    def test_liquidity_multiplier_affects_score(self):
        """Test that liquidity multiplier scales the final composite score."""
        baseline = calculate_composite_score(
            profit=40.0,
            volume=100,
            roi=25.0,
            trend_multiplier=1.0,
            volatility_penalty=1.0,
            liquidity_multiplier=1.0,
        )
        boosted = calculate_composite_score(
            profit=40.0,
            volume=100,
            roi=25.0,
            trend_multiplier=1.0,
            volatility_penalty=1.0,
            liquidity_multiplier=1.2,
        )
        assert boosted == pytest.approx(baseline * 1.2)


class TestCalculateProfitabilityScoresWithMetrics:
    """Tests for the main scoring function."""

    @pytest.mark.unit
    def test_returns_sorted_by_composite_score(
        self, sample_profit_data, sample_volume_data, sample_trend_metrics
    ):
        """Test that results are sorted by composite score descending."""
        results = calculate_profitability_scores_with_metrics(
            profit_data=sample_profit_data,
            volume_data=sample_volume_data,
            trend_volatility_metrics=sample_trend_metrics,
            strategy=StrategyType.BALANCED,
        )
        scores = [r.composite_score for r in results]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.unit
    def test_filters_by_volume_threshold_safe_strategy(
        self, sample_profit_data, sample_trend_metrics
    ):
        """Test that items below volume threshold are filtered for Safe strategy."""
        # Safe strategy requires min_volume=50
        low_volume_data = {
            "individual": {
                "saryn_prime_set": 10,  # Below 50
                "mesa_prime_set": 10,   # Below 50
                "volt_prime_set": 10,   # Below 50
            },
            "total": 30,
        }
        results = calculate_profitability_scores_with_metrics(
            profit_data=sample_profit_data,
            volume_data=low_volume_data,
            trend_volatility_metrics=sample_trend_metrics,
            strategy=StrategyType.SAFE_STEADY,
        )
        assert len(results) == 0

    @pytest.mark.unit
    def test_aggressive_strategy_accepts_low_volume(
        self, sample_profit_data, sample_trend_metrics
    ):
        """Test that Aggressive strategy accepts lower volume (min=5)."""
        low_volume_data = {
            "individual": {
                "saryn_prime_set": 10,
                "mesa_prime_set": 10,
                "volt_prime_set": 10,
            },
            "total": 30,
        }
        results = calculate_profitability_scores_with_metrics(
            profit_data=sample_profit_data,
            volume_data=low_volume_data,
            trend_volatility_metrics=sample_trend_metrics,
            strategy=StrategyType.AGGRESSIVE,
        )
        # All items should be included (volume=10 > min_volume=5)
        assert len(results) == 3

    @pytest.mark.unit
    def test_empty_input_returns_empty(self):
        """Test handling of empty input."""
        results = calculate_profitability_scores_with_metrics(
            profit_data=[],
            volume_data={},
            trend_volatility_metrics={},
        )
        assert results == []

    @pytest.mark.unit
    def test_returns_scored_data_objects(
        self, sample_profit_data, sample_volume_data, sample_trend_metrics
    ):
        """Test that results are ScoredData objects with expected fields."""
        results = calculate_profitability_scores_with_metrics(
            profit_data=sample_profit_data,
            volume_data=sample_volume_data,
            trend_volatility_metrics=sample_trend_metrics,
        )
        assert len(results) > 0
        item = results[0]
        # Check essential fields exist
        assert hasattr(item, 'set_slug')
        assert hasattr(item, 'composite_score')
        assert hasattr(item, 'trend_multiplier')
        assert hasattr(item, 'volatility_penalty')
        assert hasattr(item, 'profit_contribution')
        assert hasattr(item, 'execution_mode')
        assert hasattr(item, 'liquidity_multiplier')

    @pytest.mark.unit
    def test_uses_default_metrics_for_missing_items(self, sample_profit_data, sample_volume_data):
        """Test that default metrics are used when trend data is missing."""
        results = calculate_profitability_scores_with_metrics(
            profit_data=sample_profit_data,
            volume_data=sample_volume_data,
            trend_volatility_metrics={},  # Empty metrics
        )
        for item in results:
            # Should use defaults
            assert item.trend_multiplier == 1.0
            assert item.volatility_penalty == 1.0
            assert item.trend_direction == 'stable'

    @pytest.mark.unit
    def test_handles_integer_volume_data(self, sample_profit_data, sample_trend_metrics):
        """Test handling of integer volume data format."""
        results = calculate_profitability_scores_with_metrics(
            profit_data=sample_profit_data,
            volume_data=100,  # Single integer
            trend_volatility_metrics=sample_trend_metrics,
        )
        # Should assign volume=1 to all items
        for item in results:
            assert item.volume == 1

    @pytest.mark.unit
    def test_execution_mode_switches_profit_fields(
        self, sample_profit_data, sample_volume_data, sample_trend_metrics
    ):
        """Patient mode should score using patient profit metrics."""
        instant_results = calculate_profitability_scores_with_metrics(
            profit_data=sample_profit_data,
            volume_data=sample_volume_data,
            trend_volatility_metrics=sample_trend_metrics,
            strategy=StrategyType.BALANCED,
            execution_mode=ExecutionMode.INSTANT,
        )
        patient_results = calculate_profitability_scores_with_metrics(
            profit_data=sample_profit_data,
            volume_data=sample_volume_data,
            trend_volatility_metrics=sample_trend_metrics,
            strategy=StrategyType.BALANCED,
            execution_mode=ExecutionMode.PATIENT,
        )

        instant_by_slug = {item.set_slug: item for item in instant_results}
        patient_by_slug = {item.set_slug: item for item in patient_results}

        assert instant_by_slug["saryn_prime_set"].profit_margin == pytest.approx(30.0)
        assert patient_by_slug["saryn_prime_set"].profit_margin == pytest.approx(70.0)
        assert instant_by_slug["saryn_prime_set"].execution_mode == ExecutionMode.INSTANT
        assert patient_by_slug["saryn_prime_set"].execution_mode == ExecutionMode.PATIENT

    @pytest.mark.unit
    def test_liquidity_metrics_populated_from_orderbook(
        self, sample_profit_data, sample_volume_data, sample_trend_metrics
    ):
        """Liquidity fields should be computed when orderbook depth is available."""
        results = calculate_profitability_scores_with_metrics(
            profit_data=sample_profit_data,
            volume_data=sample_volume_data,
            trend_volatility_metrics=sample_trend_metrics,
            strategy=StrategyType.BALANCED,
            execution_mode=ExecutionMode.INSTANT,
        )

        saryn = next(item for item in results if item.set_slug == "saryn_prime_set")
        assert saryn.bid_ask_ratio > 0
        assert saryn.sell_side_competition > 0
        assert saryn.liquidity_velocity > 0
        assert saryn.liquidity_multiplier > 1.0

    @pytest.mark.unit
    def test_liquidity_defaults_when_orderbook_missing(self, sample_volume_data, sample_trend_metrics):
        """Rows without orderbook depth should keep neutral liquidity defaults."""
        profit_data = [{
            "set_slug": "legacy_set",
            "set_name": "Legacy Set",
            "set_price": 100.0,
            "part_cost": 80.0,
            "profit_margin": 20.0,
            "profit_percentage": 25.0,
            "part_details": [],
        }]
        volume_data = {"individual": {"legacy_set": 100}, "total": 100}
        results = calculate_profitability_scores_with_metrics(
            profit_data=profit_data,
            volume_data=volume_data,
            trend_volatility_metrics={},
            strategy=StrategyType.BALANCED,
        )
        assert len(results) == 1
        item = results[0]
        assert item.bid_ask_ratio == 0.0
        assert item.sell_side_competition == 0.0
        assert item.liquidity_velocity == 0.0
        assert item.liquidity_multiplier == 1.0


class TestCalculateProfitabilityScoresLegacy:
    """Tests for the legacy additive scoring function."""

    @pytest.mark.unit
    def test_returns_sorted_by_total_score(self, sample_profit_data, sample_volume_data):
        """Test that results are sorted by total score descending."""
        results = calculate_profitability_scores(
            profit_data=sample_profit_data,
            volume_data=sample_volume_data,
        )
        scores = [r.total_score for r in results]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.unit
    def test_weight_parameters_affect_score(self, sample_profit_data, sample_volume_data):
        """Test that weight parameters affect the scoring."""
        results_default = calculate_profitability_scores(
            profit_data=sample_profit_data,
            volume_data=sample_volume_data,
            profit_weight=1.0,
            volume_weight=1.2,
        )
        results_profit_heavy = calculate_profitability_scores(
            profit_data=sample_profit_data,
            volume_data=sample_volume_data,
            profit_weight=2.0,
            volume_weight=0.5,
        )
        # Scores should differ
        assert results_default[0].total_score != results_profit_heavy[0].total_score


class TestRecalculateScoresWithStrategy:
    """Tests for rescoring with different strategies."""

    @pytest.mark.unit
    def test_rescoring_changes_order(self, sample_scored_data):
        """Test that rescoring can change the order of items."""
        # Rescore with aggressive strategy
        rescored = recalculate_scores_with_strategy(
            scored_data=sample_scored_data,
            strategy=StrategyType.AGGRESSIVE,
        )
        assert len(rescored) == len(sample_scored_data)
        # Scores should be recalculated
        for item in rescored:
            assert 'composite_score' in item

    @pytest.mark.unit
    def test_rescoring_filters_by_volume(self, sample_scored_data):
        """Test that rescoring applies volume threshold filter."""
        # Add low volume item
        low_volume_item = {
            "set_slug": "low_volume_set",
            "set_name": "Low Volume Set",
            "profit_margin": 100.0,
            "profit_percentage": 100.0,
            "volume": 5,  # Below safe_steady threshold of 50
            "trend_multiplier": 1.5,
            "volatility_penalty": 1.0,
        }
        data_with_low_vol = sample_scored_data + [low_volume_item]

        rescored = recalculate_scores_with_strategy(
            scored_data=data_with_low_vol,
            strategy=StrategyType.SAFE_STEADY,
        )
        # Low volume item should be filtered out
        slugs = [item['set_slug'] for item in rescored]
        assert 'low_volume_set' not in slugs

    @pytest.mark.unit
    def test_rescoring_empty_returns_empty(self):
        """Test that rescoring empty data returns empty."""
        result = recalculate_scores_with_strategy([], StrategyType.BALANCED)
        assert result == []

    @pytest.mark.unit
    def test_rescoring_preserves_item_data(self, sample_scored_data):
        """Test that rescoring preserves original item data."""
        rescored = recalculate_scores_with_strategy(
            scored_data=sample_scored_data,
            strategy=StrategyType.BALANCED,
        )
        # Check that original fields are preserved
        for original, rescored_item in zip(sample_scored_data, rescored):
            assert rescored_item['set_slug'] == original['set_slug']
            assert rescored_item['profit_margin'] == original['profit_margin']

    @pytest.mark.unit
    def test_rescoring_can_switch_execution_mode(self, sample_scored_data):
        """Rescore should update profit fields when execution mode changes."""
        rescored = recalculate_scores_with_strategy(
            scored_data=sample_scored_data,
            strategy=StrategyType.BALANCED,
            execution_mode=ExecutionMode.PATIENT,
        )
        by_slug = {item['set_slug']: item for item in rescored}
        assert by_slug["saryn_prime_set"]["execution_mode"] == "patient"
        assert by_slug["saryn_prime_set"]["profit_margin"] == pytest.approx(70.0)
        assert by_slug["mesa_prime_set"]["profit_margin"] == pytest.approx(50.0)
