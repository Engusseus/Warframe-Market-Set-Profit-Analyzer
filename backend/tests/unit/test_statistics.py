"""Unit tests for statistics calculations."""
import pytest
import statistics as stats_module

from app.core.statistics import (
    calculate_linear_regression_slope,
    calculate_trend_multiplier,
    calculate_volatility,
    calculate_volatility_penalty,
    classify_risk_level,
    determine_trend_direction,
    calculate_metrics_from_history,
    calculate_score_contributions,
)


class TestCalculateLinearRegressionSlope:
    """Tests for linear regression slope calculation."""

    @pytest.mark.unit
    def test_rising_prices_positive_slope(self):
        """Test that rising prices give positive slope."""
        prices = [100.0, 110.0, 120.0, 130.0, 140.0]
        timestamps = [0, 1, 2, 3, 4]
        slope = calculate_linear_regression_slope(prices, timestamps)
        assert slope > 0

    @pytest.mark.unit
    def test_falling_prices_negative_slope(self):
        """Test that falling prices give negative slope."""
        prices = [140.0, 130.0, 120.0, 110.0, 100.0]
        timestamps = [0, 1, 2, 3, 4]
        slope = calculate_linear_regression_slope(prices, timestamps)
        assert slope < 0

    @pytest.mark.unit
    def test_stable_prices_zero_slope(self):
        """Test that stable prices give zero slope."""
        prices = [100.0, 100.0, 100.0, 100.0, 100.0]
        timestamps = [0, 1, 2, 3, 4]
        slope = calculate_linear_regression_slope(prices, timestamps)
        assert slope == 0.0

    @pytest.mark.unit
    def test_insufficient_data_returns_zero(self):
        """Test that insufficient data returns zero."""
        assert calculate_linear_regression_slope([100.0], [0]) == 0.0
        assert calculate_linear_regression_slope([], []) == 0.0

    @pytest.mark.unit
    def test_mismatched_lengths_returns_zero(self):
        """Test that mismatched lengths return zero."""
        prices = [100.0, 110.0, 120.0]
        timestamps = [0, 1]  # Wrong length
        slope = calculate_linear_regression_slope(prices, timestamps)
        assert slope == 0.0

    @pytest.mark.unit
    def test_linear_data_gives_exact_slope(self):
        """Test that perfectly linear data gives exact slope."""
        # y = 2x + 100
        prices = [100.0, 102.0, 104.0, 106.0, 108.0]
        timestamps = [0, 1, 2, 3, 4]
        slope = calculate_linear_regression_slope(prices, timestamps)
        assert slope == pytest.approx(2.0)


class TestCalculateTrendMultiplier:
    """Tests for trend multiplier calculation."""

    @pytest.mark.unit
    def test_zero_slope_gives_one(self):
        """Test that zero slope gives multiplier of 1.0."""
        multiplier = calculate_trend_multiplier(0.0, 100.0)
        assert multiplier == 1.0

    @pytest.mark.unit
    def test_zero_price_range_gives_one(self):
        """Test that zero price range gives multiplier of 1.0."""
        multiplier = calculate_trend_multiplier(0.5, 0.0)
        assert multiplier == 1.0

    @pytest.mark.unit
    def test_positive_slope_above_one(self):
        """Test that positive slope gives multiplier above 1.0."""
        multiplier = calculate_trend_multiplier(0.001, 100.0)
        assert multiplier > 1.0

    @pytest.mark.unit
    def test_negative_slope_below_one(self):
        """Test that negative slope gives multiplier below 1.0."""
        multiplier = calculate_trend_multiplier(-0.001, 100.0)
        assert multiplier < 1.0

    @pytest.mark.unit
    def test_clamped_to_range(self):
        """Test that multiplier is clamped to [0.5, 1.5]."""
        # Very large positive slope
        mult_high = calculate_trend_multiplier(100.0, 1.0)
        assert mult_high <= 1.5

        # Very large negative slope
        mult_low = calculate_trend_multiplier(-100.0, 1.0)
        assert mult_low >= 0.5


class TestCalculateVolatility:
    """Tests for volatility calculation."""

    @pytest.mark.unit
    def test_returns_standard_deviation(self):
        """Test that volatility is standard deviation."""
        prices = [100.0, 110.0, 90.0, 105.0, 95.0]
        volatility = calculate_volatility(prices)
        expected = stats_module.stdev(prices)
        assert volatility == pytest.approx(expected)

    @pytest.mark.unit
    def test_single_price_returns_zero(self):
        """Test that single price returns zero volatility."""
        assert calculate_volatility([100.0]) == 0.0

    @pytest.mark.unit
    def test_empty_returns_zero(self):
        """Test that empty list returns zero."""
        assert calculate_volatility([]) == 0.0

    @pytest.mark.unit
    def test_identical_prices_returns_zero(self):
        """Test that identical prices return zero volatility."""
        assert calculate_volatility([100.0, 100.0, 100.0]) == 0.0


class TestCalculateVolatilityPenalty:
    """Tests for volatility penalty calculation."""

    @pytest.mark.unit
    def test_zero_volatility_returns_one(self):
        """Test that zero volatility returns penalty of 1.0."""
        penalty = calculate_volatility_penalty(0.0, 100.0)
        assert penalty == 1.0

    @pytest.mark.unit
    def test_zero_mean_returns_one(self):
        """Test that zero mean returns penalty of 1.0."""
        penalty = calculate_volatility_penalty(10.0, 0.0)
        assert penalty == 1.0

    @pytest.mark.unit
    def test_higher_volatility_higher_penalty(self):
        """Test that higher volatility gives higher penalty."""
        penalty_low = calculate_volatility_penalty(5.0, 100.0)
        penalty_high = calculate_volatility_penalty(30.0, 100.0)
        assert penalty_high > penalty_low

    @pytest.mark.unit
    def test_clamped_to_max_penalty(self):
        """Test that penalty is clamped to max_penalty."""
        penalty = calculate_volatility_penalty(1000.0, 100.0, max_penalty=2.0)
        assert penalty <= 2.0

    @pytest.mark.unit
    def test_minimum_penalty_is_one(self):
        """Test that penalty is at least 1.0."""
        penalty = calculate_volatility_penalty(0.001, 100.0)
        assert penalty >= 1.0


class TestClassifyRiskLevel:
    """Tests for risk level classification."""

    @pytest.mark.unit
    def test_low_penalty_is_low_risk(self):
        """Test that low penalty gives Low risk."""
        assert classify_risk_level(1.0) == "Low"
        assert classify_risk_level(1.10) == "Low"
        assert classify_risk_level(1.14) == "Low"

    @pytest.mark.unit
    def test_medium_penalty_is_medium_risk(self):
        """Test that medium penalty gives Medium risk."""
        assert classify_risk_level(1.15) == "Medium"
        assert classify_risk_level(1.30) == "Medium"
        assert classify_risk_level(1.39) == "Medium"

    @pytest.mark.unit
    def test_high_penalty_is_high_risk(self):
        """Test that high penalty gives High risk."""
        assert classify_risk_level(1.40) == "High"
        assert classify_risk_level(1.5) == "High"
        assert classify_risk_level(2.0) == "High"


class TestDetermineTrendDirection:
    """Tests for trend direction determination."""

    @pytest.mark.unit
    def test_rising_trend(self):
        """Test that high multiplier is rising."""
        assert determine_trend_direction(1.1) == "rising"
        assert determine_trend_direction(1.5) == "rising"

    @pytest.mark.unit
    def test_falling_trend(self):
        """Test that low multiplier is falling."""
        assert determine_trend_direction(0.9) == "falling"
        assert determine_trend_direction(0.5) == "falling"

    @pytest.mark.unit
    def test_stable_trend(self):
        """Test that neutral multiplier is stable."""
        assert determine_trend_direction(1.0) == "stable"
        assert determine_trend_direction(1.04) == "stable"
        assert determine_trend_direction(0.96) == "stable"


class TestCalculateMetricsFromHistory:
    """Tests for calculate_metrics_from_history function."""

    @pytest.mark.unit
    def test_returns_all_metrics(self, sample_price_history):
        """Test that all metrics are returned."""
        metrics = calculate_metrics_from_history(sample_price_history)

        assert 'trend_slope' in metrics
        assert 'trend_multiplier' in metrics
        assert 'trend_direction' in metrics
        assert 'volatility' in metrics
        assert 'volatility_penalty' in metrics
        assert 'risk_level' in metrics
        assert 'data_points' in metrics

    @pytest.mark.unit
    def test_data_points_count(self, sample_price_history):
        """Test that data_points count is correct."""
        metrics = calculate_metrics_from_history(sample_price_history)
        assert metrics['data_points'] == len(sample_price_history)

    @pytest.mark.unit
    def test_empty_history_returns_defaults(self):
        """Test that empty history returns default values."""
        metrics = calculate_metrics_from_history([])

        assert metrics['trend_slope'] == 0.0
        assert metrics['trend_multiplier'] == 1.0
        assert metrics['trend_direction'] == 'stable'
        assert metrics['volatility'] == 0.0
        assert metrics['volatility_penalty'] == 1.0
        assert metrics['risk_level'] == 'Medium'
        assert metrics['data_points'] == 0

    @pytest.mark.unit
    def test_single_point_returns_defaults(self):
        """Test that single data point returns defaults."""
        metrics = calculate_metrics_from_history([
            {"lowest_price": 100.0, "timestamp": 1000}
        ])

        assert metrics['trend_multiplier'] == 1.0
        assert metrics['data_points'] == 1

    @pytest.mark.unit
    def test_ignores_invalid_entries_and_sorts_history(self):
        """Test that invalid points are ignored and valid points are processed."""
        metrics = calculate_metrics_from_history([
            {"lowest_price": 120.0, "timestamp": 3},
            {"lowest_price": "bad", "timestamp": 2},
            {"lowest_price": 100.0, "timestamp": 1},
            {"timestamp": 4},
        ])

        assert metrics['data_points'] == 2
        assert metrics['trend_direction'] == "rising"


class TestCalculateScoreContributions:
    """Tests for score contribution calculation."""

    @pytest.mark.unit
    def test_returns_five_values(self):
        """Test that five contribution values are returned."""
        result = calculate_score_contributions(
            profit=50.0,
            volume=100,
            roi=50.0,
            trend_multiplier=1.0,
            volatility_penalty=1.0,
        )
        assert len(result) == 5

    @pytest.mark.unit
    def test_profit_contribution_equals_profit(self):
        """Test that profit contribution equals profit."""
        result = calculate_score_contributions(
            profit=50.0,
            volume=100,
            roi=50.0,
            trend_multiplier=1.0,
            volatility_penalty=1.0,
        )
        profit_contrib, _, _, _, _ = result
        assert profit_contrib == 50.0

    @pytest.mark.unit
    def test_volume_contribution_is_log(self):
        """Test that volume contribution is log10(volume)."""
        result = calculate_score_contributions(
            profit=50.0,
            volume=100,
            roi=50.0,
            trend_multiplier=1.0,
            volatility_penalty=1.0,
        )
        _, volume_contrib, _, _, _ = result
        assert volume_contrib == pytest.approx(2.0)  # log10(100) = 2

    @pytest.mark.unit
    def test_roi_contribution_formula(self):
        """Test that ROI contribution follows formula."""
        result = calculate_score_contributions(
            profit=50.0,
            volume=100,
            roi=50.0,
            trend_multiplier=1.0,
            volatility_penalty=1.0,
        )
        _, _, roi_contrib, _, _ = result
        # ROI factor = 1.0 + (50/100) = 1.5
        assert roi_contrib == pytest.approx(1.5)
