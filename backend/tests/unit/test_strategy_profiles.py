"""Unit tests for strategy profiles."""
import pytest

from app.core.strategy_profiles import (
    StrategyType,
    StrategyProfile,
    STRATEGY_PROFILES,
    get_strategy_profile,
    apply_strategy_weights,
    get_all_strategies,
)


class TestStrategyProfiles:
    """Tests for strategy profile definitions."""

    @pytest.mark.unit
    def test_all_strategies_defined(self):
        """Test that all strategy types have profiles defined."""
        for strategy_type in StrategyType:
            assert strategy_type in STRATEGY_PROFILES

    @pytest.mark.unit
    def test_safe_steady_profile_values(self):
        """Test Safe & Steady profile has expected values."""
        profile = STRATEGY_PROFILES[StrategyType.SAFE_STEADY]
        assert profile.volatility_weight == 2.0  # Strong volatility penalty
        assert profile.trend_weight == 0.5       # Less trend emphasis
        assert profile.roi_weight == 0.8         # Moderate ROI
        assert profile.min_volume_threshold == 50  # High liquidity required

    @pytest.mark.unit
    def test_balanced_profile_values(self):
        """Test Balanced profile has neutral values."""
        profile = STRATEGY_PROFILES[StrategyType.BALANCED]
        assert profile.volatility_weight == 1.0
        assert profile.trend_weight == 1.0
        assert profile.roi_weight == 1.0
        assert profile.min_volume_threshold == 10

    @pytest.mark.unit
    def test_aggressive_profile_values(self):
        """Test Aggressive profile has expected values."""
        profile = STRATEGY_PROFILES[StrategyType.AGGRESSIVE]
        assert profile.volatility_weight == 0.5  # Tolerates volatility
        assert profile.trend_weight == 1.5       # Strong trend emphasis
        assert profile.roi_weight == 1.5         # Strong ROI emphasis
        assert profile.min_volume_threshold == 5   # Low volume acceptable

    @pytest.mark.unit
    def test_profiles_have_names_and_descriptions(self):
        """Test that all profiles have names and descriptions."""
        for profile in STRATEGY_PROFILES.values():
            assert profile.name
            assert profile.description
            assert len(profile.name) > 0
            assert len(profile.description) > 0


class TestGetStrategyProfile:
    """Tests for get_strategy_profile function."""

    @pytest.mark.unit
    def test_returns_correct_profile(self):
        """Test that correct profile is returned for each type."""
        for strategy_type in StrategyType:
            profile = get_strategy_profile(strategy_type)
            assert isinstance(profile, StrategyProfile)
            assert profile == STRATEGY_PROFILES[strategy_type]

    @pytest.mark.unit
    def test_invalid_strategy_raises_error(self):
        """Test that invalid strategy raises KeyError."""
        with pytest.raises(KeyError):
            get_strategy_profile("invalid_strategy")


class TestApplyStrategyWeights:
    """Tests for apply_strategy_weights function."""

    @pytest.mark.unit
    def test_balanced_strategy_neutral(self):
        """Test that balanced strategy applies neutral weights."""
        base_score = 100.0
        score = apply_strategy_weights(
            base_score=base_score,
            volatility_penalty=1.0,
            trend_multiplier=1.0,
            roi=0.0,
            strategy=StrategyType.BALANCED,
        )
        # With all neutral inputs, score should equal base_score
        assert score == pytest.approx(base_score)

    @pytest.mark.unit
    def test_safe_strategy_penalizes_volatility_more(self):
        """Test that Safe strategy applies stronger volatility penalty."""
        base_score = 100.0
        volatility_penalty = 1.5  # Above baseline

        safe_score = apply_strategy_weights(
            base_score=base_score,
            volatility_penalty=volatility_penalty,
            trend_multiplier=1.0,
            roi=0.0,
            strategy=StrategyType.SAFE_STEADY,
        )
        balanced_score = apply_strategy_weights(
            base_score=base_score,
            volatility_penalty=volatility_penalty,
            trend_multiplier=1.0,
            roi=0.0,
            strategy=StrategyType.BALANCED,
        )
        # Safe strategy should have lower score due to stronger penalty
        assert safe_score < balanced_score

    @pytest.mark.unit
    def test_aggressive_strategy_tolerates_volatility(self):
        """Test that Aggressive strategy is more tolerant of volatility."""
        base_score = 100.0
        volatility_penalty = 1.5

        aggressive_score = apply_strategy_weights(
            base_score=base_score,
            volatility_penalty=volatility_penalty,
            trend_multiplier=1.0,
            roi=0.0,
            strategy=StrategyType.AGGRESSIVE,
        )
        balanced_score = apply_strategy_weights(
            base_score=base_score,
            volatility_penalty=volatility_penalty,
            trend_multiplier=1.0,
            roi=0.0,
            strategy=StrategyType.BALANCED,
        )
        # Aggressive strategy should have higher score (less penalty)
        assert aggressive_score > balanced_score

    @pytest.mark.unit
    def test_aggressive_strategy_emphasizes_trend(self):
        """Test that Aggressive strategy emphasizes positive trends."""
        base_score = 100.0
        trend_multiplier = 1.3  # Rising trend

        aggressive_score = apply_strategy_weights(
            base_score=base_score,
            volatility_penalty=1.0,
            trend_multiplier=trend_multiplier,
            roi=0.0,
            strategy=StrategyType.AGGRESSIVE,
        )
        balanced_score = apply_strategy_weights(
            base_score=base_score,
            volatility_penalty=1.0,
            trend_multiplier=trend_multiplier,
            roi=0.0,
            strategy=StrategyType.BALANCED,
        )
        # Aggressive should benefit more from rising trend
        assert aggressive_score > balanced_score

    @pytest.mark.unit
    def test_safe_strategy_dampens_trend_impact(self):
        """Test that Safe strategy reduces trend impact."""
        base_score = 100.0
        trend_multiplier = 1.3

        safe_score = apply_strategy_weights(
            base_score=base_score,
            volatility_penalty=1.0,
            trend_multiplier=trend_multiplier,
            roi=0.0,
            strategy=StrategyType.SAFE_STEADY,
        )
        balanced_score = apply_strategy_weights(
            base_score=base_score,
            volatility_penalty=1.0,
            trend_multiplier=trend_multiplier,
            roi=0.0,
            strategy=StrategyType.BALANCED,
        )
        # Safe strategy should have lower score (less trend boost)
        assert safe_score < balanced_score

    @pytest.mark.unit
    def test_roi_weight_affects_score(self):
        """Test that ROI weight affects score differently per strategy."""
        base_score = 100.0
        roi = 50.0  # 50% ROI

        aggressive_score = apply_strategy_weights(
            base_score=base_score,
            volatility_penalty=1.0,
            trend_multiplier=1.0,
            roi=roi,
            strategy=StrategyType.AGGRESSIVE,
        )
        safe_score = apply_strategy_weights(
            base_score=base_score,
            volatility_penalty=1.0,
            trend_multiplier=1.0,
            roi=roi,
            strategy=StrategyType.SAFE_STEADY,
        )
        # Aggressive should benefit more from high ROI
        assert aggressive_score > safe_score

    @pytest.mark.unit
    def test_negative_base_negative_roi_increases_magnitude(self):
        """Test sign-preserving ROI behavior for negative base scores."""
        base_score = -100.0

        score_without_roi = apply_strategy_weights(
            base_score=base_score,
            volatility_penalty=1.0,
            trend_multiplier=1.0,
            roi=0.0,
            strategy=StrategyType.BALANCED,
        )
        score_with_negative_roi = apply_strategy_weights(
            base_score=base_score,
            volatility_penalty=1.0,
            trend_multiplier=1.0,
            roi=-50.0,
            strategy=StrategyType.BALANCED,
        )

        assert score_with_negative_roi < score_without_roi
        assert abs(score_with_negative_roi) > abs(score_without_roi)
        assert score_with_negative_roi == pytest.approx(-150.0)

    @pytest.mark.unit
    def test_negative_base_positive_roi_decreases_magnitude(self):
        """Test that opposing ROI direction dampens negative base score."""
        base_score = -100.0

        score_without_roi = apply_strategy_weights(
            base_score=base_score,
            volatility_penalty=1.0,
            trend_multiplier=1.0,
            roi=0.0,
            strategy=StrategyType.BALANCED,
        )
        score_with_positive_roi = apply_strategy_weights(
            base_score=base_score,
            volatility_penalty=1.0,
            trend_multiplier=1.0,
            roi=50.0,
            strategy=StrategyType.BALANCED,
        )

        assert abs(score_with_positive_roi) < abs(score_without_roi)
        assert score_with_positive_roi == pytest.approx(-50.0)


class TestGetAllStrategies:
    """Tests for get_all_strategies function."""

    @pytest.mark.unit
    def test_returns_all_strategies(self):
        """Test that all strategies are returned."""
        strategies = get_all_strategies()
        assert len(strategies) == 3

    @pytest.mark.unit
    def test_returns_correct_format(self):
        """Test that returned data has correct format."""
        strategies = get_all_strategies()
        for strategy in strategies:
            assert 'type' in strategy
            assert 'name' in strategy
            assert 'description' in strategy
            assert 'volatility_weight' in strategy
            assert 'trend_weight' in strategy
            assert 'roi_weight' in strategy
            assert 'min_volume_threshold' in strategy

    @pytest.mark.unit
    def test_type_values_match_enum(self):
        """Test that type values match StrategyType enum values."""
        strategies = get_all_strategies()
        strategy_types = [s['type'] for s in strategies]
        expected_types = [st.value for st in StrategyType]
        assert set(strategy_types) == set(expected_types)
