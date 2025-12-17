"""Statistical calculations for trend analysis and volatility.

This module provides functions for calculating price trends using linear regression
and market volatility metrics for risk assessment.
"""
import math
import statistics
from typing import Dict, List, Tuple


def calculate_linear_regression_slope(
    prices: List[float],
    timestamps: List[int]
) -> float:
    """Calculate the slope of a linear regression line for price data.

    Uses simple linear regression (least squares) to determine the trend direction
    and magnitude of price changes over time.

    Args:
        prices: List of price values (y-axis)
        timestamps: List of corresponding Unix timestamps (x-axis)

    Returns:
        The slope of the regression line (price change per second).
        Positive = rising prices, negative = falling prices.
        Returns 0 if insufficient data points.
    """
    n = len(prices)
    if n < 2 or len(timestamps) != n:
        return 0.0

    # Calculate means
    mean_x = sum(timestamps) / n
    mean_y = sum(prices) / n

    # Calculate slope using least squares formula
    # slope = sum((x - mean_x)(y - mean_y)) / sum((x - mean_x)^2)
    numerator = sum((timestamps[i] - mean_x) * (prices[i] - mean_y) for i in range(n))
    denominator = sum((timestamps[i] - mean_x) ** 2 for i in range(n))

    if denominator == 0:
        return 0.0

    return numerator / denominator


def calculate_trend_multiplier(
    slope: float,
    price_range: float,
    time_span_seconds: int = 7 * 24 * 3600
) -> float:
    """Convert a regression slope to a trend multiplier.

    Maps the slope to a multiplier in the range [0.5, 1.5] where:
    - Rising prices (positive slope) -> multiplier > 1.0
    - Falling prices (negative slope) -> multiplier < 1.0
    - Stable prices (zero slope) -> multiplier = 1.0

    The slope is normalized relative to the price range to account for
    different price magnitudes across items.

    Args:
        slope: The regression slope (price change per second)
        price_range: The difference between max and min prices in the period
        time_span_seconds: The time span for normalization (default 7 days)

    Returns:
        A multiplier in the range [0.5, 1.5]
    """
    if price_range <= 0 or slope == 0:
        return 1.0

    # Calculate expected price change over the time span
    expected_change = slope * time_span_seconds

    # Normalize relative to price range to get a percentage-like value
    # This makes the trend comparable across items with different price levels
    normalized_change = expected_change / price_range

    # Map to multiplier range [0.5, 1.5]
    # A normalized change of +1 (price increased by full range) -> 1.5
    # A normalized change of -1 (price decreased by full range) -> 0.5
    # Clamp to reasonable bounds
    multiplier = 1.0 + (normalized_change * 0.5)
    return max(0.5, min(1.5, multiplier))


def calculate_volatility(prices: List[float]) -> float:
    """Calculate the standard deviation of prices.

    Args:
        prices: List of price values

    Returns:
        Standard deviation of prices. Returns 0 if insufficient data.
    """
    if len(prices) < 2:
        return 0.0

    return statistics.stdev(prices)


def calculate_volatility_penalty(
    volatility: float,
    mean_price: float,
    max_penalty: float = 2.0
) -> float:
    """Convert volatility to a penalty factor.

    Uses the coefficient of variation (CV = std_dev / mean) to create a
    scale-independent volatility measure, then maps it to a penalty range.

    Args:
        volatility: Standard deviation of prices
        mean_price: Mean price value
        max_penalty: Maximum penalty factor (default 2.0)

    Returns:
        A penalty factor in the range [1.0, max_penalty].
        - Low volatility (CV < 0.05) -> penalty ~ 1.0
        - Medium volatility (CV ~ 0.15) -> penalty ~ 1.3
        - High volatility (CV > 0.30) -> penalty approaches max_penalty
    """
    if mean_price <= 0 or volatility <= 0:
        return 1.0

    # Calculate coefficient of variation
    cv = volatility / mean_price

    # Map CV to penalty range [1.0, max_penalty]
    # Using a logarithmic-like curve for smoother scaling
    # CV of 0.30 (30% variation) should give roughly 1.5x penalty
    # CV of 0.50 (50% variation) should approach max_penalty
    penalty = 1.0 + (cv * 3.0)  # Linear scaling: 10% CV = 1.3 penalty
    return max(1.0, min(max_penalty, penalty))


def classify_risk_level(volatility_penalty: float) -> str:
    """Classify risk level based on volatility penalty.

    Args:
        volatility_penalty: The calculated volatility penalty factor

    Returns:
        "Low", "Medium", or "High" risk classification
    """
    if volatility_penalty < 1.15:
        return "Low"
    elif volatility_penalty < 1.40:
        return "Medium"
    else:
        return "High"


def determine_trend_direction(trend_multiplier: float) -> str:
    """Determine the trend direction based on the trend multiplier.

    Args:
        trend_multiplier: The calculated trend multiplier

    Returns:
        "rising", "falling", or "stable"
    """
    if trend_multiplier > 1.05:
        return "rising"
    elif trend_multiplier < 0.95:
        return "falling"
    else:
        return "stable"


def calculate_metrics_from_history(
    price_history: List[Dict[str, float]]
) -> Dict[str, float]:
    """Calculate all trend and volatility metrics from price history.

    This is a convenience function that calculates all metrics in one call.

    Args:
        price_history: List of dicts with 'lowest_price' and 'timestamp' keys,
                      ordered chronologically (oldest first)

    Returns:
        Dictionary containing:
        - trend_slope: Raw slope value
        - trend_multiplier: Mapped multiplier [0.5, 1.5]
        - trend_direction: "rising", "falling", or "stable"
        - volatility: Standard deviation
        - volatility_penalty: Mapped penalty [1.0, 2.0]
        - risk_level: "Low", "Medium", or "High"
        - data_points: Number of data points used
    """
    if not price_history or len(price_history) < 2:
        return {
            'trend_slope': 0.0,
            'trend_multiplier': 1.0,
            'trend_direction': 'stable',
            'volatility': 0.0,
            'volatility_penalty': 1.0,
            'risk_level': 'Medium',
            'data_points': len(price_history) if price_history else 0
        }

    # Extract prices and timestamps
    prices = [h['lowest_price'] for h in price_history]
    timestamps = [h['timestamp'] for h in price_history]

    # Calculate trend metrics
    slope = calculate_linear_regression_slope(prices, timestamps)
    price_range = max(prices) - min(prices)
    time_span = timestamps[-1] - timestamps[0] if len(timestamps) > 1 else 7 * 24 * 3600
    trend_multiplier = calculate_trend_multiplier(slope, price_range, time_span)
    trend_direction = determine_trend_direction(trend_multiplier)

    # Calculate volatility metrics
    volatility = calculate_volatility(prices)
    mean_price = statistics.mean(prices)
    volatility_penalty = calculate_volatility_penalty(volatility, mean_price)
    risk_level = classify_risk_level(volatility_penalty)

    return {
        'trend_slope': slope,
        'trend_multiplier': trend_multiplier,
        'trend_direction': trend_direction,
        'volatility': volatility,
        'volatility_penalty': volatility_penalty,
        'risk_level': risk_level,
        'data_points': len(price_history)
    }


def calculate_score_contributions(
    profit: float,
    volume: int,
    roi: float,
    trend_multiplier: float,
    volatility_penalty: float
) -> Tuple[float, float, float, float, float]:
    """Calculate individual factor contributions to the composite score.

    This is useful for the "Golden Formula" breakdown in the UI.

    Args:
        profit: Profit margin in platinum
        volume: 48-hour trading volume
        roi: Return on investment percentage
        trend_multiplier: Trend multiplier [0.5, 1.5]
        volatility_penalty: Volatility penalty [1.0, 2.0]

    Returns:
        Tuple of (profit_contribution, volume_contribution, roi_contribution,
                  trend_contribution, volatility_contribution)
    """
    # Volume contribution (logarithmic)
    volume_factor = max(math.log10(max(volume, 1)), 0.1)

    # Base score: profit * log(volume)
    base_score = profit * volume_factor

    # ROI factor: multiply by (1 + roi/100)
    roi_factor = 1.0 + (roi / 100.0)

    # Calculate step-by-step contributions
    profit_contribution = profit
    volume_contribution = volume_factor
    roi_contribution = roi_factor
    trend_contribution = trend_multiplier
    volatility_contribution = volatility_penalty

    return (
        profit_contribution,
        volume_contribution,
        roi_contribution,
        trend_contribution,
        volatility_contribution
    )
