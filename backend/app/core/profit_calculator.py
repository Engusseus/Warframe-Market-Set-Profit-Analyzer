"""Profit margin calculation.

Extracted from main.py lines 749-835.
"""
from typing import Any, Dict, List

from ..models.schemas import PartDetail, ProfitData


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Convert value to float safely."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_quantity(value: Any, default: int = 1) -> int:
    """Convert quantity value to positive int safely."""
    try:
        quantity = int(float(value))
    except (TypeError, ValueError):
        return default
    return quantity if quantity > 0 else default


def _coalesce_positive(*values: Any, default: float = 0.0) -> float:
    """Return first positive numeric value."""
    for value in values:
        numeric = _safe_float(value)
        if numeric > 0:
            return numeric
    return default


def _normalize_levels(raw_levels: Any) -> List[Dict[str, Any]]:
    """Normalize orderbook levels to [{'platinum': float, 'quantity': int}, ...]."""
    if not isinstance(raw_levels, list):
        return []

    levels: List[Dict[str, Any]] = []
    for entry in raw_levels:
        if not isinstance(entry, dict):
            continue

        price = _safe_float(entry.get('platinum', entry.get('price')))
        if price <= 0:
            continue

        quantity = _safe_quantity(entry.get('quantity'), default=1)
        if quantity <= 0:
            continue

        levels.append({
            'platinum': price,
            'quantity': quantity,
        })

    return levels


def _calculate_vwap_total(
    levels: List[Dict[str, Any]],
    required_quantity: int,
    fallback_unit_price: float,
    descending: bool = False
) -> float:
    """Calculate total execution notional using orderbook depth and fallback price."""
    if required_quantity <= 0:
        return 0.0

    ordered_levels = sorted(
        levels,
        key=lambda level: _safe_float(level.get('platinum')),
        reverse=descending
    )

    remaining = required_quantity
    total_cost = 0.0

    for level in ordered_levels:
        level_price = _safe_float(level.get('platinum'))
        level_quantity = _safe_quantity(level.get('quantity'), default=0)
        if level_price <= 0 or level_quantity <= 0:
            continue

        take_quantity = min(remaining, level_quantity)
        total_cost += level_price * take_quantity
        remaining -= take_quantity
        if remaining == 0:
            break

    if remaining > 0:
        fallback = _safe_float(fallback_unit_price)
        if ordered_levels:
            # If visible depth is insufficient, continue at the worst displayed
            # level instead of the best quote to reduce phantom-profit bias.
            depth_edge_price = _safe_float(ordered_levels[-1].get('platinum'))
            if depth_edge_price > 0:
                fallback = depth_edge_price
        if fallback <= 0:
            return 0.0
        total_cost += fallback * remaining

    return total_cost


def _compute_profit_rows(
    set_prices: List[Dict[str, Any]],
    part_prices: List[Dict[str, Any]],
    detailed_sets: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Compute profit rows in plain-dict form for reuse across APIs."""
    if not set_prices or not part_prices or not detailed_sets:
        return []

    set_price_lookup = {
        item['slug']: item for item in set_prices
        if isinstance(item, dict) and item.get('slug')
    }
    part_price_lookup = {
        item['slug']: item for item in part_prices
        if isinstance(item, dict) and item.get('slug')
    }

    rows: List[Dict[str, Any]] = []
    for set_data in detailed_sets:
        set_slug = set_data.get('slug', '')
        if not set_slug:
            continue

        set_price_data = set_price_lookup.get(set_slug)
        if not isinstance(set_price_data, dict):
            continue

        set_lowest_price = _safe_float(set_price_data.get('lowest_price'))
        set_highest_bid = _coalesce_positive(set_price_data.get('highest_bid'))
        set_sell_levels = _normalize_levels(set_price_data.get('top_sell_orders'))
        set_buy_levels = _normalize_levels(set_price_data.get('top_buy_orders'))

        instant_set_fallback = _coalesce_positive(set_highest_bid, set_lowest_price)
        patient_set_fallback = _coalesce_positive(set_lowest_price, set_highest_bid)

        instant_set_price = _calculate_vwap_total(
            set_buy_levels,
            required_quantity=1,
            fallback_unit_price=instant_set_fallback,
            descending=True
        )
        patient_set_price = _calculate_vwap_total(
            set_sell_levels,
            required_quantity=1,
            fallback_unit_price=patient_set_fallback,
            descending=False
        )

        if instant_set_price <= 0:
            continue

        set_name = set_data.get('name', 'Unknown Set')
        total_instant_part_cost = 0.0
        total_patient_part_cost = 0.0
        part_details: List[Dict[str, Any]] = []
        missing_part = False

        for part in set_data.get('setParts', []):
            part_code = part.get('code', '')
            if not part_code:
                missing_part = True
                break

            part_price_data = part_price_lookup.get(part_code)
            if not isinstance(part_price_data, dict):
                missing_part = True
                break

            quantity_needed = _safe_quantity(
                part.get('quantityInSet', part_price_data.get('quantity_in_set', 1)),
                default=1
            )

            part_lowest_price = _safe_float(part_price_data.get('lowest_price'))
            part_highest_bid = _coalesce_positive(part_price_data.get('highest_bid'))
            part_sell_levels = _normalize_levels(part_price_data.get('top_sell_orders'))
            part_buy_levels = _normalize_levels(part_price_data.get('top_buy_orders'))

            instant_part_fallback = _coalesce_positive(part_lowest_price, part_highest_bid)
            patient_part_fallback = _coalesce_positive(part_highest_bid, part_lowest_price)

            instant_total_cost = _calculate_vwap_total(
                part_sell_levels,
                required_quantity=quantity_needed,
                fallback_unit_price=instant_part_fallback,
                descending=False
            )
            patient_total_cost = _calculate_vwap_total(
                part_buy_levels,
                required_quantity=quantity_needed,
                fallback_unit_price=patient_part_fallback,
                descending=True
            )

            if instant_total_cost <= 0 or patient_total_cost <= 0:
                missing_part = True
                break

            total_instant_part_cost += instant_total_cost
            total_patient_part_cost += patient_total_cost

            instant_unit_price = instant_total_cost / quantity_needed
            patient_unit_price = patient_total_cost / quantity_needed
            part_details.append({
                'name': part.get('name', 'Unknown Part'),
                'code': part_code,
                'unit_price': instant_unit_price,
                'quantity': quantity_needed,
                'total_cost': instant_total_cost,
                'lowest_price': part_lowest_price,
                'highest_bid': part_highest_bid,
                'top_sell_orders': part_sell_levels,
                'top_buy_orders': part_buy_levels,
                'instant_unit_price': instant_unit_price,
                'patient_unit_price': patient_unit_price,
                'instant_total_cost': instant_total_cost,
                'patient_total_cost': patient_total_cost,
            })

        if missing_part or total_instant_part_cost <= 0:
            continue

        instant_profit_margin = instant_set_price - total_instant_part_cost
        instant_profit_percentage = (instant_profit_margin / total_instant_part_cost) * 100
        patient_profit_margin = patient_set_price - total_patient_part_cost
        patient_profit_percentage = (
            (patient_profit_margin / total_patient_part_cost) * 100
            if total_patient_part_cost > 0 else 0.0
        )

        rows.append({
            'set_slug': set_slug,
            'set_name': set_name,
            'set_price': instant_set_price,
            'part_cost': total_instant_part_cost,
            'profit_margin': instant_profit_margin,
            'profit_percentage': instant_profit_percentage,
            'set_lowest_price': set_lowest_price,
            'set_highest_bid': set_highest_bid,
            'set_top_sell_orders': set_sell_levels,
            'set_top_buy_orders': set_buy_levels,
            'instant_set_price': instant_set_price,
            'instant_part_cost': total_instant_part_cost,
            'instant_profit_margin': instant_profit_margin,
            'instant_profit_percentage': instant_profit_percentage,
            'patient_set_price': patient_set_price,
            'patient_part_cost': total_patient_part_cost,
            'patient_profit_margin': patient_profit_margin,
            'patient_profit_percentage': patient_profit_percentage,
            'part_details': part_details,
        })

    return rows


def calculate_profit_margins(
    set_prices: List[Dict[str, Any]],
    part_prices: List[Dict[str, Any]],
    detailed_sets: List[Dict[str, Any]]
) -> List[ProfitData]:
    """Calculate profit margins for each set with orderbook-aware execution prices.

    This is the core business logic that determines profitability.

    Args:
        set_prices: List of set pricing data with keys: slug, lowest_price, highest_bid
        part_prices: List of part pricing data with keys: slug, lowest_price, highest_bid
        detailed_sets: List of detailed set information from cache

    Returns:
        List of ProfitData objects for each viable set

    Formula:
        instant_profit_margin = instant_set_price - instant_part_cost
        instant_profit_percentage = (instant_profit_margin / instant_part_cost) * 100
    """
    rows = _compute_profit_rows(set_prices, part_prices, detailed_sets)
    return [
        ProfitData(
            set_slug=row['set_slug'],
            set_name=row['set_name'],
            set_price=row['set_price'],
            part_cost=row['part_cost'],
            profit_margin=row['profit_margin'],
            profit_percentage=row['profit_percentage'],
            instant_set_price=row['instant_set_price'],
            instant_part_cost=row['instant_part_cost'],
            instant_profit_margin=row['instant_profit_margin'],
            instant_profit_percentage=row['instant_profit_percentage'],
            patient_set_price=row['patient_set_price'],
            patient_part_cost=row['patient_part_cost'],
            patient_profit_margin=row['patient_profit_margin'],
            patient_profit_percentage=row['patient_profit_percentage'],
            part_details=[PartDetail(**part) for part in row['part_details']]
        )
        for row in rows
    ]


def calculate_profit_margins_dict(
    set_prices: List[Dict[str, Any]],
    part_prices: List[Dict[str, Any]],
    detailed_sets: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Calculate profit margins returning dictionaries for backwards compatibility.

    This version returns plain dicts instead of Pydantic models.
    """
    return _compute_profit_rows(set_prices, part_prices, detailed_sets)
