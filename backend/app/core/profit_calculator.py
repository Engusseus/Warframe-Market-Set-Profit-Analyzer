"""Profit margin calculation.

Extracted from main.py lines 749-835.
"""
from typing import Any, Dict, List

from ..models.schemas import PartDetail, ProfitData


def _compute_profit_rows(
    set_prices: List[Dict[str, Any]],
    part_prices: List[Dict[str, Any]],
    detailed_sets: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Compute profit rows in plain-dict form for reuse across APIs."""
    if not set_prices or not part_prices or not detailed_sets:
        return []

    set_price_lookup = {item['slug']: item['lowest_price'] for item in set_prices}
    part_price_lookup = {item['slug']: item['lowest_price'] for item in part_prices}

    rows: List[Dict[str, Any]] = []
    for set_data in detailed_sets:
        set_slug = set_data.get('slug', '')
        if not set_slug:
            continue

        set_lowest_price = set_price_lookup.get(set_slug)
        if set_lowest_price is None:
            continue

        set_name = set_data.get('name', 'Unknown Set')
        total_part_cost = 0.0
        part_details = []
        missing_part = False

        for part in set_data.get('setParts', []):
            part_code = part.get('code', '')
            if not part_code:
                missing_part = True
                break

            unit_price = part_price_lookup.get(part_code)
            if unit_price is None:
                missing_part = True
                break

            quantity_needed = part.get('quantityInSet', 1)
            part_total_cost = unit_price * quantity_needed
            total_part_cost += part_total_cost
            part_details.append({
                'name': part.get('name', 'Unknown Part'),
                'code': part_code,
                'unit_price': unit_price,
                'quantity': quantity_needed,
                'total_cost': part_total_cost
            })

        if missing_part or total_part_cost <= 0:
            continue

        profit_margin = set_lowest_price - total_part_cost
        profit_percentage = (profit_margin / total_part_cost) * 100
        rows.append({
            'set_slug': set_slug,
            'set_name': set_name,
            'set_price': set_lowest_price,
            'part_cost': total_part_cost,
            'profit_margin': profit_margin,
            'profit_percentage': profit_percentage,
            'part_details': part_details
        })

    return rows


def calculate_profit_margins(
    set_prices: List[Dict[str, Any]],
    part_prices: List[Dict[str, Any]],
    detailed_sets: List[Dict[str, Any]]
) -> List[ProfitData]:
    """Calculate profit margins for each set by comparing set price to sum of part prices.

    This is the core business logic that determines profitability.

    Args:
        set_prices: List of set pricing data with keys: slug, lowest_price
        part_prices: List of part pricing data with keys: slug, lowest_price, quantity_in_set
        detailed_sets: List of detailed set information from cache

    Returns:
        List of ProfitData objects for each viable set

    Formula:
        profit_margin = set_price - total_part_cost
        profit_percentage = (profit_margin / total_part_cost) * 100
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
