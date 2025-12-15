"""Profitability scoring algorithms.

Extracted from main.py lines 928-1001.
"""
from typing import Any, Dict, List, Union

from .normalization import normalize_data
from ..models.schemas import ScoredData


def calculate_profitability_scores(
    profit_data: List[Dict[str, Any]],
    volume_data: Union[Dict[str, Any], int, float, List[Dict[str, Any]]],
    profit_weight: float = 1.0,
    volume_weight: float = 1.2
) -> List[ScoredData]:
    """Calculate profitability scores combining profit and volume data.

    This is the weighted scoring algorithm that ranks sets by trading opportunity.

    Args:
        profit_data: List of profit analysis results (from calculate_profit_margins)
        volume_data: Dict with 'individual' key mapping slugs to volumes,
                    or legacy format (int/float for total, or list)
        profit_weight: Weight for profit factor (default: 1.0)
        volume_weight: Weight for volume factor (default: 1.2)

    Returns:
        List of ScoredData objects sorted by total score (descending)

    Formula:
        total_score = (normalized_profit * profit_weight) + (normalized_volume * volume_weight)
    """
    if not profit_data:
        return []

    # Handle different volume data formats
    volume_lookup: Dict[str, int] = {}

    if isinstance(volume_data, dict) and 'individual' in volume_data:
        # New format with individual volumes
        volume_lookup = volume_data['individual'].copy()
    elif isinstance(volume_data, (int, float)):
        # Legacy format - total volume only
        # Set all volumes to 1 so they don't affect relative scoring
        for item in profit_data:
            volume_lookup[item['set_slug']] = 1
    else:
        # Handle other legacy formats
        if isinstance(volume_data, list):
            for item in volume_data:
                if isinstance(item, dict) and 'set_slug' in item:
                    volume_lookup[item['set_slug']] = item.get('volume', 0)
        else:
            # Default to equal volumes
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

        # Handle part_details - could be dicts or Pydantic models
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
            volume=volume_values[i],
            normalized_profit=normalized_profits[i],
            normalized_volume=normalized_volumes[i],
            profit_score=profit_score,
            volume_score=volume_score,
            total_score=total_score
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
    """Calculate profitability scores returning dictionaries for backwards compatibility."""
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
            'volume': volume_values[i],
            'normalized_profit': normalized_profits[i],
            'normalized_volume': normalized_volumes[i],
            'profit_score': profit_score,
            'volume_score': volume_score,
            'total_score': total_score
        })

    scored_data.sort(key=lambda x: x['total_score'], reverse=True)

    return scored_data


def recalculate_scores_with_new_weights(
    scored_data: List[Dict[str, Any]],
    new_weights: tuple,
    old_weights: tuple
) -> List[Dict[str, Any]]:
    """Recalculate profitability scores with new weights.

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

        rescored_data.append(item_copy)

    # Re-sort by new scores
    rescored_data.sort(key=lambda x: x['total_score'], reverse=True)

    return rescored_data
