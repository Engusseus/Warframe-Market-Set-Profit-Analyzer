"""Profitability scoring algorithms.

This module implements a multiplicative scoring model:
    Score = (Profit * log10(Volume)) * ROI_factor * TrendMultiplier / VolatilityPenalty

Where ROI_factor is sign-preserving for negative opportunities.

The scoring system supports strategy profiles that adjust how each factor
contributes to the final score.
"""
import math
from typing import Any, Dict, List, Tuple, Union

from .normalization import normalize_data
from .roi import calculate_sign_preserving_roi_factor
from .strategy_profiles import StrategyType, apply_strategy_weights, get_strategy_profile
from .statistics import calculate_score_contributions
from ..models.schemas import ExecutionMode, ScoredData


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Convert value to float safely."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    """Convert value to non-negative int safely."""
    try:
        numeric = int(float(value))
    except (TypeError, ValueError):
        return default
    return numeric if numeric >= 0 else default


def _resolve_execution_mode(mode: Union[ExecutionMode, str]) -> ExecutionMode:
    """Normalize execution mode input with safe default for backwards compatibility."""
    if isinstance(mode, ExecutionMode):
        return mode
    try:
        return ExecutionMode(str(mode).strip().lower())
    except (TypeError, ValueError):
        return ExecutionMode.INSTANT


def _normalize_orderbook_levels(raw_levels: Any) -> List[Dict[str, float]]:
    """Normalize orderbook entries to consistent numeric shape."""
    if not isinstance(raw_levels, list):
        return []

    levels: List[Dict[str, float]] = []
    for entry in raw_levels:
        if not isinstance(entry, dict):
            continue

        price = _safe_float(entry.get('platinum', entry.get('price')), 0.0)
        quantity = _safe_int(entry.get('quantity'), 0)
        if price <= 0 or quantity <= 0:
            continue

        levels.append({'platinum': price, 'quantity': float(quantity)})

    return levels


def _calculate_liquidity_metrics(profit_item: Dict[str, Any]) -> Tuple[float, float, float, float]:
    """Calculate liquidity metrics from set-level orderbook data."""
    buy_levels = _normalize_orderbook_levels(profit_item.get('set_top_buy_orders'))
    sell_levels = _normalize_orderbook_levels(profit_item.get('set_top_sell_orders'))

    if not buy_levels and not sell_levels:
        # Historical rows may not include orderbook depth.
        return 0.0, 0.0, 0.0, 1.0

    best_bid = _safe_float(profit_item.get('set_highest_bid'), 0.0)
    best_ask = _safe_float(profit_item.get('set_lowest_price'), 0.0)

    if best_bid <= 0 and buy_levels:
        best_bid = max(level['platinum'] for level in buy_levels)
    if best_ask <= 0 and sell_levels:
        best_ask = min(level['platinum'] for level in sell_levels)

    bid_ask_ratio = 0.0
    if best_bid > 0 and best_ask > 0:
        bid_ask_ratio = max(min(best_bid / best_ask, 1.5), 0.0)

    buy_depth = sum(level['quantity'] for level in buy_levels)
    sell_depth = sum(level['quantity'] for level in sell_levels)

    if buy_depth <= 0 and sell_depth <= 0:
        return bid_ask_ratio, 0.0, 0.0, 1.0

    sell_side_competition = sell_depth / max(buy_depth, 1.0)
    liquidity_velocity = bid_ask_ratio / max(sell_side_competition, 0.1)
    liquidity_velocity = max(min(liquidity_velocity, 2.0), 0.0)

    liquidity_multiplier = 0.8 + (0.2 * liquidity_velocity)
    liquidity_multiplier = max(min(liquidity_multiplier, 1.2), 0.8)

    return bid_ask_ratio, sell_side_competition, liquidity_velocity, liquidity_multiplier


def _resolve_execution_values(
    profit_item: Dict[str, Any],
    execution_mode: ExecutionMode
) -> Tuple[float, float, float, float]:
    """Resolve set price, part cost, profit and ROI for selected execution mode."""
    if execution_mode == ExecutionMode.PATIENT:
        set_price = _safe_float(
            profit_item.get('patient_set_price', profit_item.get('set_price', 0.0)),
            0.0
        )
        part_cost = _safe_float(
            profit_item.get('patient_part_cost', profit_item.get('part_cost', 0.0)),
            0.0
        )
        profit = _safe_float(
            profit_item.get('patient_profit_margin', profit_item.get('profit_margin', 0.0)),
            0.0
        )
        roi = _safe_float(
            profit_item.get('patient_profit_percentage', profit_item.get('profit_percentage', 0.0)),
            0.0
        )
        return set_price, part_cost, profit, roi

    set_price = _safe_float(
        profit_item.get('instant_set_price', profit_item.get('set_price', 0.0)),
        0.0
    )
    part_cost = _safe_float(
        profit_item.get('instant_part_cost', profit_item.get('part_cost', 0.0)),
        0.0
    )
    profit = _safe_float(
        profit_item.get('instant_profit_margin', profit_item.get('profit_margin', 0.0)),
        0.0
    )
    roi = _safe_float(
        profit_item.get('instant_profit_percentage', profit_item.get('profit_percentage', 0.0)),
        0.0
    )
    return set_price, part_cost, profit, roi


def calculate_composite_score(
    profit: float,
    volume: int,
    roi: float,
    trend_multiplier: float,
    volatility_penalty: float,
    liquidity_multiplier: float = 1.0
) -> float:
    """Calculate the composite score using the multiplicative formula.

    Golden Formula:
        Score = (Profit * log10(Volume)) * ROI_factor * TrendMultiplier / VolatilityPenalty

    Args:
        profit: Profit margin in platinum
        volume: 48-hour trading volume
        roi: Return on investment percentage
        trend_multiplier: Trend multiplier [0.5, 1.5]
        volatility_penalty: Volatility penalty [1.0, 2.0]
        liquidity_multiplier: Liquidity multiplier [0.8, 1.2]

    Returns:
        The composite score. Can be negative for unprofitable items.
    """
    # Handle volume edge case - avoid log(0)
    volume_factor = max(math.log10(max(volume, 1)), 0.1)

    # Base score: profit * log(volume)
    base_score = profit * volume_factor

    # Apply ROI as a sign-preserving multiplier.
    roi_factor = calculate_sign_preserving_roi_factor(base_score=base_score, roi=roi)
    roi_adjusted = base_score * roi_factor

    # Apply trend multiplier
    trend_adjusted = roi_adjusted * trend_multiplier

    # Apply volatility penalty
    final_score = trend_adjusted / volatility_penalty

    # Apply liquidity multiplier
    return final_score * liquidity_multiplier


def calculate_profitability_scores_with_metrics(
    profit_data: List[Dict[str, Any]],
    volume_data: Union[Dict[str, Any], int, float, List[Dict[str, Any]]],
    trend_volatility_metrics: Dict[str, Dict[str, Any]],
    strategy: StrategyType = StrategyType.BALANCED,
    execution_mode: Union[ExecutionMode, str] = ExecutionMode.INSTANT
) -> List[ScoredData]:
    """Calculate profitability scores with trend and volatility metrics.

    This is the main scoring function for the trading engine.

    Args:
        profit_data: List of profit analysis results (from calculate_profit_margins)
        volume_data: Dict with 'individual' key mapping slugs to volumes
        trend_volatility_metrics: Dict mapping set_slug to trend/volatility metrics
        strategy: Trading strategy to apply
        execution_mode: Whether to score using instant or patient execution metrics

    Returns:
        List of ScoredData objects sorted by composite score (descending)
    """
    if not profit_data:
        return []

    profile = get_strategy_profile(strategy)
    selected_mode = _resolve_execution_mode(execution_mode)

    # Handle different volume data formats
    volume_lookup: Dict[str, int] = {}

    if isinstance(volume_data, dict) and 'individual' in volume_data:
        volume_lookup = volume_data['individual'].copy()
    elif isinstance(volume_data, (int, float)):
        for item in profit_data:
            volume_lookup[item['set_slug']] = 1
    else:
        if isinstance(volume_data, list):
            for item in volume_data:
                if isinstance(item, dict) and 'set_slug' in item:
                    volume_lookup[item['set_slug']] = item.get('volume', 0)
        else:
            for item in profit_data:
                volume_lookup[item['set_slug']] = 1

    # Calculate scores for each item
    scored_data = []
    for profit_item in profit_data:
        set_slug = profit_item['set_slug']
        volume = volume_lookup.get(set_slug, 0)

        # Skip items below volume threshold for this strategy
        if volume < profile.min_volume_threshold:
            continue

        # Get trend/volatility metrics (use defaults if not available)
        metrics = trend_volatility_metrics.get(set_slug, {})
        trend_slope = metrics.get('trend_slope', 0.0)
        trend_multiplier = metrics.get('trend_multiplier', 1.0)
        trend_direction = metrics.get('trend_direction', 'stable')
        volatility = metrics.get('volatility', 0.0)
        volatility_penalty = metrics.get('volatility_penalty', 1.0)
        risk_level = metrics.get('risk_level', 'Medium')
        set_price, part_cost, profit, roi = _resolve_execution_values(
            profit_item,
            selected_mode
        )
        bid_ask_ratio, sell_side_competition, liquidity_velocity, liquidity_multiplier = \
            _calculate_liquidity_metrics(profit_item)

        # Calculate base score (profit * log(volume))
        volume_factor = max(math.log10(max(volume, 1)), 0.1)
        base_score = profit * volume_factor

        # Apply strategy weights for composite score
        weighted_score = apply_strategy_weights(
            base_score=base_score,
            volatility_penalty=volatility_penalty,
            trend_multiplier=trend_multiplier,
            roi=roi,
            strategy=strategy
        )
        composite_score = weighted_score * liquidity_multiplier

        # Calculate contributions for UI breakdown
        profit_contrib, volume_contrib, _, trend_contrib, vol_contrib = \
            calculate_score_contributions(
                profit=profit,
                volume=volume,
                roi=roi,
                trend_multiplier=trend_multiplier,
                volatility_penalty=volatility_penalty
            )

        # Handle part_details - could be dicts or Pydantic models
        part_details = profit_item.get('part_details', [])
        if part_details and hasattr(part_details[0], 'model_dump'):
            part_details = [p.model_dump() for p in part_details]

        # Calculate legacy normalized values for backward compatibility
        # These will be recalculated after all items are processed

        scored_data.append(ScoredData(
            set_slug=set_slug,
            set_name=profit_item.get('set_name', ''),
            set_price=set_price,
            part_cost=part_cost,
            profit_margin=profit,
            profit_percentage=roi,
            part_details=part_details,
            execution_mode=selected_mode,
            instant_set_price=profit_item.get('instant_set_price', profit_item.get('set_price')),
            instant_part_cost=profit_item.get('instant_part_cost', profit_item.get('part_cost')),
            instant_profit_margin=profit_item.get('instant_profit_margin', profit_item.get('profit_margin')),
            instant_profit_percentage=profit_item.get('instant_profit_percentage', profit_item.get('profit_percentage')),
            patient_set_price=profit_item.get('patient_set_price', profit_item.get('set_price')),
            patient_part_cost=profit_item.get('patient_part_cost', profit_item.get('part_cost')),
            patient_profit_margin=profit_item.get('patient_profit_margin', profit_item.get('profit_margin')),
            patient_profit_percentage=profit_item.get('patient_profit_percentage', profit_item.get('profit_percentage')),
            volume=volume,
            # New composite scoring fields
            trend_slope=trend_slope,
            trend_multiplier=trend_multiplier,
            trend_direction=trend_direction,
            volatility=volatility,
            volatility_penalty=volatility_penalty,
            risk_level=risk_level,
            composite_score=composite_score,
            profit_contribution=profit_contrib,
            volume_contribution=volume_contrib,
            trend_contribution=trend_contrib,
            volatility_contribution=vol_contrib,
            bid_ask_ratio=bid_ask_ratio,
            sell_side_competition=sell_side_competition,
            liquidity_velocity=liquidity_velocity,
            liquidity_multiplier=liquidity_multiplier,
            # Legacy fields for backward compatibility
            normalized_profit=0.0,  # Will be set below
            normalized_volume=0.0,  # Will be set below
            profit_score=0.0,       # Will be set below
            volume_score=0.0,       # Will be set below
            total_score=composite_score  # Mirror composite_score
        ))

    # Calculate legacy normalized scores for backward compatibility
    if scored_data:
        profit_values = [s.profit_margin for s in scored_data]
        volume_values = [s.volume for s in scored_data]
        normalized_profits = normalize_data(profit_values)
        normalized_volumes = normalize_data(volume_values)

        for i, item in enumerate(scored_data):
            item.normalized_profit = normalized_profits[i]
            item.normalized_volume = normalized_volumes[i]
            item.profit_score = normalized_profits[i]
            item.volume_score = normalized_volumes[i]

    # Sort by composite score (descending)
    scored_data.sort(key=lambda x: x.composite_score, reverse=True)

    return scored_data


def calculate_profitability_scores(
    profit_data: List[Dict[str, Any]],
    volume_data: Union[Dict[str, Any], int, float, List[Dict[str, Any]]],
    profit_weight: float = 1.0,
    volume_weight: float = 1.2
) -> List[ScoredData]:
    """Calculate profitability scores using legacy additive method.

    DEPRECATED: Use calculate_profitability_scores_with_metrics() instead.

    This function is kept for backward compatibility. It uses the old additive
    formula without trend/volatility metrics.

    Args:
        profit_data: List of profit analysis results
        volume_data: Dict with 'individual' key mapping slugs to volumes
        profit_weight: Weight for profit factor (default: 1.0)
        volume_weight: Weight for volume factor (default: 1.2)

    Returns:
        List of ScoredData objects sorted by total score (descending)
    """
    if not profit_data:
        return []

    # Handle different volume data formats
    volume_lookup: Dict[str, int] = {}

    if isinstance(volume_data, dict) and 'individual' in volume_data:
        volume_lookup = volume_data['individual'].copy()
    elif isinstance(volume_data, (int, float)):
        for item in profit_data:
            volume_lookup[item['set_slug']] = 1
    else:
        if isinstance(volume_data, list):
            for item in volume_data:
                if isinstance(item, dict) and 'set_slug' in item:
                    volume_lookup[item['set_slug']] = item.get('volume', 0)
        else:
            for item in profit_data:
                volume_lookup[item['set_slug']] = 1

    # Extract values for normalization
    profit_values = [item['profit_margin'] for item in profit_data]
    volume_values = []

    for item in profit_data:
        set_slug = item['set_slug']
        volume = volume_lookup.get(set_slug, 0)
        volume_values.append(volume)

    # Normalize both datasets to 0-1 range
    normalized_profits = normalize_data(profit_values)
    normalized_volumes = normalize_data(volume_values)

    # Calculate weighted scores
    scored_data = []
    for i, profit_item in enumerate(profit_data):
        profit_score = normalized_profits[i] * profit_weight
        volume_score = normalized_volumes[i] * volume_weight
        total_score = profit_score + volume_score

        # Handle part_details
        part_details = profit_item.get('part_details', [])
        if part_details and hasattr(part_details[0], 'model_dump'):
            part_details = [p.model_dump() for p in part_details]

        scored_data.append(ScoredData(
            set_slug=profit_item['set_slug'],
            set_name=profit_item['set_name'],
            set_price=profit_item['set_price'],
            part_cost=profit_item['part_cost'],
            profit_margin=profit_item['profit_margin'],
            profit_percentage=profit_item['profit_percentage'],
            part_details=part_details,
            execution_mode=ExecutionMode.INSTANT,
            instant_set_price=profit_item.get('instant_set_price', profit_item.get('set_price')),
            instant_part_cost=profit_item.get('instant_part_cost', profit_item.get('part_cost')),
            instant_profit_margin=profit_item.get('instant_profit_margin', profit_item.get('profit_margin')),
            instant_profit_percentage=profit_item.get('instant_profit_percentage', profit_item.get('profit_percentage')),
            patient_set_price=profit_item.get('patient_set_price', profit_item.get('set_price')),
            patient_part_cost=profit_item.get('patient_part_cost', profit_item.get('part_cost')),
            patient_profit_margin=profit_item.get('patient_profit_margin', profit_item.get('profit_margin')),
            patient_profit_percentage=profit_item.get('patient_profit_percentage', profit_item.get('profit_percentage')),
            volume=volume_values[i],
            normalized_profit=normalized_profits[i],
            normalized_volume=normalized_volumes[i],
            profit_score=profit_score,
            volume_score=volume_score,
            total_score=total_score,
            # New fields with defaults
            trend_slope=0.0,
            trend_multiplier=1.0,
            trend_direction='stable',
            volatility=0.0,
            volatility_penalty=1.0,
            risk_level='Medium',
            composite_score=total_score,
            profit_contribution=profit_item['profit_margin'],
            volume_contribution=max(math.log10(max(volume_values[i], 1)), 0.1),
            trend_contribution=1.0,
            volatility_contribution=1.0,
            bid_ask_ratio=0.0,
            sell_side_competition=0.0,
            liquidity_velocity=0.0,
            liquidity_multiplier=1.0
        ))

    # Sort by total score (descending)
    scored_data.sort(key=lambda x: x.total_score, reverse=True)

    return scored_data


def calculate_profitability_scores_dict(
    profit_data: List[Dict[str, Any]],
    volume_data: Union[Dict[str, Any], int, float, List[Dict[str, Any]]],
    profit_weight: float = 1.0,
    volume_weight: float = 1.2
) -> List[Dict[str, Any]]:
    """Calculate profitability scores returning dictionaries.

    DEPRECATED: Use calculate_profitability_scores_with_metrics() instead.
    """
    if not profit_data:
        return []

    volume_lookup: Dict[str, int] = {}

    if isinstance(volume_data, dict) and 'individual' in volume_data:
        volume_lookup = volume_data['individual'].copy()
    elif isinstance(volume_data, (int, float)):
        for item in profit_data:
            volume_lookup[item['set_slug']] = 1
    else:
        if isinstance(volume_data, list):
            for item in volume_data:
                if isinstance(item, dict) and 'set_slug' in item:
                    volume_lookup[item['set_slug']] = item.get('volume', 0)
        else:
            for item in profit_data:
                volume_lookup[item['set_slug']] = 1

    profit_values = [item['profit_margin'] for item in profit_data]
    volume_values = []

    for item in profit_data:
        set_slug = item['set_slug']
        volume = volume_lookup.get(set_slug, 0)
        volume_values.append(volume)

    normalized_profits = normalize_data(profit_values)
    normalized_volumes = normalize_data(volume_values)

    scored_data = []
    for i, profit_item in enumerate(profit_data):
        profit_score = normalized_profits[i] * profit_weight
        volume_score = normalized_volumes[i] * volume_weight
        total_score = profit_score + volume_score

        scored_data.append({
            **profit_item,
            'execution_mode': ExecutionMode.INSTANT.value,
            'volume': volume_values[i],
            'normalized_profit': normalized_profits[i],
            'normalized_volume': normalized_volumes[i],
            'profit_score': profit_score,
            'volume_score': volume_score,
            'total_score': total_score,
            # New fields with defaults
            'trend_slope': 0.0,
            'trend_multiplier': 1.0,
            'trend_direction': 'stable',
            'volatility': 0.0,
            'volatility_penalty': 1.0,
            'risk_level': 'Medium',
            'composite_score': total_score,
            'profit_contribution': profit_item['profit_margin'],
            'volume_contribution': max(math.log10(max(volume_values[i], 1)), 0.1),
            'trend_contribution': 1.0,
            'volatility_contribution': 1.0,
            'bid_ask_ratio': 0.0,
            'sell_side_competition': 0.0,
            'liquidity_velocity': 0.0,
            'liquidity_multiplier': 1.0
        })

    scored_data.sort(key=lambda x: x['total_score'], reverse=True)

    return scored_data


def recalculate_scores_with_strategy(
    scored_data: List[Dict[str, Any]],
    strategy: StrategyType,
    execution_mode: Union[ExecutionMode, str, None] = None
) -> List[Dict[str, Any]]:
    """Recalculate scores using a different strategy.

    This allows rescoring without refetching data.

    Args:
        scored_data: Previously scored data with trend/volatility metrics
        strategy: New strategy to apply
        execution_mode: Optional mode override. If omitted, keeps existing values.

    Returns:
        Re-sorted list with new composite scores
    """
    if not scored_data:
        return scored_data

    profile = get_strategy_profile(strategy)
    selected_mode = _resolve_execution_mode(execution_mode) if execution_mode is not None else None
    rescored_data = []

    for item in scored_data:
        item_copy = item.copy()

        # Skip items below volume threshold
        volume = item.get('volume', 0)
        if volume < profile.min_volume_threshold:
            continue

        if selected_mode is None:
            set_price = _safe_float(item.get('set_price', 0.0), 0.0)
            part_cost = _safe_float(item.get('part_cost', 0.0), 0.0)
            profit = _safe_float(item.get('profit_margin', 0.0), 0.0)
            roi = _safe_float(item.get('profit_percentage', 0.0), 0.0)
            mode_value = item.get('execution_mode', ExecutionMode.INSTANT.value)
        else:
            set_price, part_cost, profit, roi = _resolve_execution_values(item, selected_mode)
            mode_value = selected_mode.value
        trend_multiplier = _safe_float(item.get('trend_multiplier', 1.0), 1.0)
        volatility_penalty = _safe_float(item.get('volatility_penalty', 1.0), 1.0)

        has_orderbook_depth = bool(item.get('set_top_buy_orders') or item.get('set_top_sell_orders'))
        if has_orderbook_depth:
            bid_ask_ratio, sell_side_competition, liquidity_velocity, liquidity_multiplier = \
                _calculate_liquidity_metrics(item)
        else:
            bid_ask_ratio = _safe_float(item.get('bid_ask_ratio', 0.0), 0.0)
            sell_side_competition = _safe_float(item.get('sell_side_competition', 0.0), 0.0)
            liquidity_velocity = _safe_float(item.get('liquidity_velocity', 0.0), 0.0)
            liquidity_multiplier = _safe_float(item.get('liquidity_multiplier', 1.0), 1.0)
            if liquidity_multiplier <= 0:
                liquidity_multiplier = 1.0

        # Calculate base score
        volume_factor = max(math.log10(max(volume, 1)), 0.1)
        base_score = profit * volume_factor

        # Apply strategy weights
        composite_score = apply_strategy_weights(
            base_score=base_score,
            volatility_penalty=volatility_penalty,
            trend_multiplier=trend_multiplier,
            roi=roi,
            strategy=strategy
        )
        composite_score *= liquidity_multiplier

        profit_contrib, volume_contrib, _, trend_contrib, vol_contrib = \
            calculate_score_contributions(
                profit=profit,
                volume=volume,
                roi=roi,
                trend_multiplier=trend_multiplier,
                volatility_penalty=volatility_penalty
            )

        item_copy['set_price'] = set_price
        item_copy['part_cost'] = part_cost
        item_copy['profit_margin'] = profit
        item_copy['profit_percentage'] = roi
        item_copy['execution_mode'] = mode_value
        item_copy['composite_score'] = composite_score
        item_copy['total_score'] = composite_score  # Mirror for backward compatibility
        item_copy['profit_contribution'] = profit_contrib
        item_copy['volume_contribution'] = volume_contrib
        item_copy['trend_contribution'] = trend_contrib
        item_copy['volatility_contribution'] = vol_contrib
        item_copy['bid_ask_ratio'] = bid_ask_ratio
        item_copy['sell_side_competition'] = sell_side_competition
        item_copy['liquidity_velocity'] = liquidity_velocity
        item_copy['liquidity_multiplier'] = liquidity_multiplier

        rescored_data.append(item_copy)

    # Re-sort by composite score
    rescored_data.sort(key=lambda x: x['composite_score'], reverse=True)

    return rescored_data


def recalculate_scores_with_new_weights(
    scored_data: List[Dict[str, Any]],
    new_weights: tuple,
    old_weights: tuple
) -> List[Dict[str, Any]]:
    """Recalculate profitability scores with new weights.

    DEPRECATED: Use recalculate_scores_with_strategy() instead.

    Args:
        scored_data: Previously scored data
        new_weights: Tuple of (profit_weight, volume_weight)
        old_weights: Previous weights (unused but kept for API compatibility)

    Returns:
        Re-sorted list with new scores
    """
    if not scored_data:
        return scored_data

    new_profit_weight, new_volume_weight = new_weights

    # Extract all profit margins and volumes for renormalization
    profit_margins = [item['profit_margin'] for item in scored_data]
    volumes = [item.get('volume', 0) for item in scored_data]

    # Normalize values
    normalized_profits = normalize_data(profit_margins)
    normalized_volumes = normalize_data(volumes)

    # Recalculate scores with new weights
    rescored_data = []
    for i, item in enumerate(scored_data):
        item_copy = item.copy()
        normalized_profit = normalized_profits[i] if normalized_profits else 0
        normalized_volume = normalized_volumes[i] if normalized_volumes else 0

        # Calculate new weighted score
        profit_score = normalized_profit * new_profit_weight
        volume_score = normalized_volume * new_volume_weight
        total_score = profit_score + volume_score

        item_copy['normalized_profit'] = normalized_profit
        item_copy['normalized_volume'] = normalized_volume
        item_copy['profit_score'] = profit_score
        item_copy['volume_score'] = volume_score
        item_copy['total_score'] = total_score
        item_copy['composite_score'] = total_score  # Mirror for compatibility

        rescored_data.append(item_copy)

    # Re-sort by new scores
    rescored_data.sort(key=lambda x: x['total_score'], reverse=True)

    return rescored_data
