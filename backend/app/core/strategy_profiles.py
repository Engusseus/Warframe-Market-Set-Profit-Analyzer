"""Trading strategy profiles for score calculation.

Defines different trading strategies that adjust how the composite score
weights various factors (volatility, trend, ROI).
"""
from dataclasses import dataclass
from enum import Enum
from typing import Dict


class StrategyType(str, Enum):
    """Available trading strategy types."""
    SAFE_STEADY = "safe_steady"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"


@dataclass
class StrategyProfile:
    """Configuration for a trading strategy.

    Attributes:
        name: Human-readable strategy name
        description: Brief description of the strategy's approach
        volatility_weight: How much to penalize volatility (higher = more penalty)
        trend_weight: How much to emphasize trends (higher = more impact)
        roi_weight: How much to emphasize ROI (higher = more impact)
        min_volume_threshold: Minimum volume required for consideration
    """
    name: str
    description: str
    volatility_weight: float
    trend_weight: float
    roi_weight: float
    min_volume_threshold: int


# Strategy profile definitions
STRATEGY_PROFILES: Dict[StrategyType, StrategyProfile] = {
    StrategyType.SAFE_STEADY: StrategyProfile(
        name="Safe & Steady",
        description="Prioritizes low volatility and stable profits. Best for risk-averse traders.",
        volatility_weight=2.0,   # Strong penalty for volatile items
        trend_weight=0.5,        # Less emphasis on trends
        roi_weight=0.8,          # Moderate ROI emphasis
        min_volume_threshold=50  # Requires higher liquidity
    ),
    StrategyType.BALANCED: StrategyProfile(
        name="Balanced",
        description="Equal consideration of all factors. Good for general trading.",
        volatility_weight=1.0,
        trend_weight=1.0,
        roi_weight=1.0,
        min_volume_threshold=10
    ),
    StrategyType.AGGRESSIVE: StrategyProfile(
        name="Aggressive Growth",
        description="Prioritizes high ROI and positive trends. Tolerates volatility for higher gains.",
        volatility_weight=0.5,   # Tolerates volatility
        trend_weight=1.5,        # Strong trend emphasis
        roi_weight=1.5,          # Strong ROI emphasis
        min_volume_threshold=5   # Lower volume acceptable
    )
}


def get_strategy_profile(strategy: StrategyType) -> StrategyProfile:
    """Get the profile configuration for a strategy type.

    Args:
        strategy: The strategy type to get the profile for

    Returns:
        The StrategyProfile for the given strategy type
    """
    return STRATEGY_PROFILES[strategy]


def apply_strategy_weights(
    base_score: float,
    volatility_penalty: float,
    trend_multiplier: float,
    roi: float,
    strategy: StrategyType
) -> float:
    """Apply strategy-specific weights to calculate the final composite score.

    The base formula is:
        Score = (Profit * log10(Volume)) * ROI * TrendMultiplier / VolatilityPenalty

    This function modifies how strongly each factor affects the final score
    based on the chosen strategy.

    Args:
        base_score: The base score (profit * log10(volume))
        volatility_penalty: Raw volatility penalty [1.0, 2.0]
        trend_multiplier: Raw trend multiplier [0.5, 1.5]
        roi: Return on investment percentage
        strategy: The trading strategy to apply

    Returns:
        The strategy-adjusted composite score
    """
    profile = STRATEGY_PROFILES[strategy]

    # Adjust volatility penalty based on strategy
    # Higher weight = penalty has more impact
    adjusted_penalty = 1.0 + (volatility_penalty - 1.0) * profile.volatility_weight

    # Adjust trend multiplier based on strategy
    # Higher weight = trend deviations have more impact
    adjusted_trend = 1.0 + (trend_multiplier - 1.0) * profile.trend_weight

    # Adjust ROI contribution based on strategy
    # Higher weight = ROI has more impact
    roi_factor = 1.0 + (roi / 100.0) * profile.roi_weight

    # Calculate final score
    score = (base_score * roi_factor * adjusted_trend) / adjusted_penalty

    return score


def get_all_strategies() -> list:
    """Get all available strategy profiles as a list of dicts.

    Returns:
        List of strategy information dictionaries
    """
    return [
        {
            'type': strategy_type.value,
            'name': profile.name,
            'description': profile.description,
            'volatility_weight': profile.volatility_weight,
            'trend_weight': profile.trend_weight,
            'roi_weight': profile.roi_weight,
            'min_volume_threshold': profile.min_volume_threshold
        }
        for strategy_type, profile in STRATEGY_PROFILES.items()
    ]
