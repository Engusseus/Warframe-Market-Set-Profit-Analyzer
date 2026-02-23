"""Statistical calculations for trend analysis and volatility.

This module provides functions for calculating price trends using linear regression
and market volatility metrics for risk assessment.
"""
import math
import statistics
from typing import Dict, List, Tuple

from .roi import calculate_sign_preserving_roi_factor


def _calculate_percentile(sorted_values: List[float], percentile: float) -> float:
    """Calculate percentile with linear interpolation.

    Args:
        sorted_values: Values sorted ascending.
        percentile: Percentile in [0, 100].

    Returns:
        Interpolated percentile value or 0.0 if empty input.
    """
    if not sorted_values:
        return 0.0

    if len(sorted_values) == 1:
        return sorted_values[0]

    bounded_percentile = max(0.0, min(100.0, percentile))
    position = (len(sorted_values) - 1) * (bounded_percentile / 100.0)
    lower_index = int(math.floor(position))
    upper_index = int(math.ceil(position))

    if lower_index == upper_index:
        return sorted_values[lower_index]

    weight = position - lower_index
    return (
        sorted_values[lower_index]
        + (sorted_values[upper_index] - sorted_values[lower_index]) * weight
    )


def _calculate_robust_trend_range(prices: List[float]) -> float:
    """Calculate a robust price range for trend normalization.

    Uses IQR (Q3 - Q1) as the primary range estimate. If IQR is zero, falls
    back to a bounded percentile range (P90 - P10), and finally to max-min.
    """
    if len(prices) < 2:
        return 0.0

    sorted_prices = sorted(prices)

    q1 = _calculate_percentile(sorted_prices, 25.0)
    q3 = _calculate_percentile(sorted_prices, 75.0)
    iqr = q3 - q1
    if iqr > 0:
        return iqr

    p10 = _calculate_percentile(sorted_prices, 10.0)
    p90 = _calculate_percentile(sorted_prices, 90.0)
    bounded_percentile_range = p90 - p10
    if bounded_percentile_range > 0:
        return bounded_percentile_range

    return sorted_prices[-1] - sorted_prices[0]


def _calculate_ema_series(values: List[float], period: int) -> List[float]:
    """Calculate EMA series for the given values."""
    if not values:
        return []

    alpha = 2.0 / (period + 1.0)
    ema = values[0]
    ema_series: List[float] = []

    for value in values:
        ema = (alpha * value) + ((1.0 - alpha) * ema)
        ema_series.append(ema)

    return ema_series


def _calculate_macd_histogram(prices: List[float]) -> float:
    """Calculate MACD histogram value from the price series."""
    if len(prices) < 3:
        return 0.0

    count = len(prices)
    fast_period = max(2, min(12, max(2, round(count * 0.35))))
    slow_period = max(fast_period + 1, min(26, max(3, round(count * 0.70))))
    signal_period = max(2, min(9, max(2, round(count * 0.25))))

    fast_ema = _calculate_ema_series(prices, fast_period)
    slow_ema = _calculate_ema_series(prices, slow_period)
    macd_line = [fast - slow for fast, slow in zip(fast_ema, slow_ema)]
    signal_line = _calculate_ema_series(macd_line, signal_period)

    return macd_line[-1] - signal_line[-1]


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
    """Calculate volatility as standard deviation of log returns.

    Args:
        prices: List of price values

    Returns:
        Standard deviation of log returns. Returns 0 if insufficient data.
    """
    if len(prices) < 2:
        return 0.0

    log_returns: List[float] = []

    for previous_price, current_price in zip(prices, prices[1:]):
        if previous_price <= 0 or current_price <= 0:
            continue
        log_returns.append(math.log(current_price / previous_price))

    if len(log_returns) < 2:
        return 0.0

    return statistics.stdev(log_returns)


def calculate_volatility_penalty(
    volatility: float,
    mean_price: float,
    max_penalty: float = 2.0
) -> float:
    """Convert volatility to a penalty factor.

    Uses log-return volatility directly (already scale independent) and maps
    it to a penalty range.

    Args:
        volatility: Standard deviation of log returns
        mean_price: Mean price value (kept for API compatibility)
        max_penalty: Maximum penalty factor (default 2.0)

    Returns:
        A penalty factor in the range [1.0, max_penalty].
        - Low volatility (~0.03) -> penalty ~ 1.1
        - Medium volatility (~0.10) -> penalty ~ 1.3
        - High volatility (>0.30) -> penalty approaches max_penalty
    """
    if volatility <= 0:
        return 1.0

    # Mean price is intentionally unused for compatibility with existing API.
    _ = mean_price

    # Map log-return volatility to penalty range [1.0, max_penalty].
    penalty = 1.0 + (volatility * 3.0)
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
    if not price_history:
        return {
            'trend_slope': 0.0,
            'trend_multiplier': 1.0,
            'trend_direction': 'stable',
            'volatility': 0.0,
            'volatility_penalty': 1.0,
            'risk_level': 'Medium',
            'data_points': 0
        }

    cleaned_history = []
    for entry in price_history:
        if not isinstance(entry, dict):
            continue
        price = entry.get('lowest_price')
        timestamp = entry.get('timestamp')
        if isinstance(price, (int, float)) and isinstance(timestamp, (int, float)):
            cleaned_history.append({
                'lowest_price': float(price),
                'timestamp': int(timestamp)
            })

    if len(cleaned_history) < 2:
        return {
            'trend_slope': 0.0,
            'trend_multiplier': 1.0,
            'trend_direction': 'stable',
            'volatility': 0.0,
            'volatility_penalty': 1.0,
            'risk_level': 'Medium',
            'data_points': len(cleaned_history)
        }

    # Ensure chronological ordering before trend analysis.
    cleaned_history.sort(key=lambda item: item['timestamp'])

    # Extract prices and timestamps
    prices = [h['lowest_price'] for h in cleaned_history]
    timestamps = [h['timestamp'] for h in cleaned_history]

    # Calculate trend metrics
    slope = calculate_linear_regression_slope(prices, timestamps)
    robust_range = _calculate_robust_trend_range(prices)
    time_span = max(timestamps[-1] - timestamps[0], 1)

    # Use MACD-style momentum for the trend multiplier while preserving
    # regression slope in output for backward compatibility.
    if len(prices) >= 3:
        macd_histogram = _calculate_macd_histogram(prices)
        macd_sensitivity = 6.0
        momentum_change = macd_histogram * macd_sensitivity
        trend_slope_equivalent = momentum_change / time_span
    else:
        trend_slope_equivalent = slope

    trend_multiplier = calculate_trend_multiplier(
        trend_slope_equivalent,
        robust_range,
        time_span
    )
    trend_direction = determine_trend_direction(trend_multiplier)

    # Calculate volatility metrics
    volatility = calculate_volatility(prices)
    mean_price = statistics.fmean(prices)
    volatility_penalty = calculate_volatility_penalty(volatility, mean_price)
    risk_level = classify_risk_level(volatility_penalty)

    return {
        'trend_slope': slope,
        'trend_multiplier': trend_multiplier,
        'trend_direction': trend_direction,
        'volatility': volatility,
        'volatility_penalty': volatility_penalty,
        'risk_level': risk_level,
        'data_points': len(cleaned_history)
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

    # ROI contribution mirrors the sign-preserving score adjustment.
    roi_factor = calculate_sign_preserving_roi_factor(base_score=base_score, roi=roi)

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
