"""Profit margin calculation.

Extracted from main.py lines 749-835.
"""
from typing import Any, Dict, List

from ..models.schemas import PartDetail, ProfitData


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
    profit_data = []

    if not set_prices or not part_prices or not detailed_sets:
        return profit_data

    # Create lookup dictionaries for faster access
    set_price_lookup = {item['slug']: item for item in set_prices}
    part_price_lookup = {item['slug']: item for item in part_prices}

    for set_data in detailed_sets:
        set_slug = set_data.get('slug', '')
        set_name = set_data.get('name', 'Unknown Set')

        if not set_slug or set_slug not in set_price_lookup:
            continue

        set_price_data = set_price_lookup[set_slug]
        set_lowest_price = set_price_data['lowest_price']

        # Calculate total cost of individual parts
        total_part_cost = 0.0
        missing_parts = []
        part_details = []

        for part in set_data.get('setParts', []):
            part_code = part.get('code', '')
            part_name = part.get('name', 'Unknown Part')
            quantity_needed = part.get('quantityInSet', 1)

            if part_code in part_price_lookup:
                part_price_data = part_price_lookup[part_code]
                part_lowest_price = part_price_data['lowest_price']
                part_total_cost = part_lowest_price * quantity_needed
                total_part_cost += part_total_cost

                part_details.append(PartDetail(
                    name=part_name,
                    code=part_code,
                    unit_price=part_lowest_price,
                    quantity=quantity_needed,
                    total_cost=part_total_cost
                ))
            else:
                missing_parts.append(part_name)

        # Skip sets with missing part data
        if missing_parts:
            continue

        # Calculate profit margin
        if total_part_cost > 0:
            profit_margin = set_lowest_price - total_part_cost
            profit_percentage = (profit_margin / total_part_cost) * 100

            profit_data.append(ProfitData(
                set_slug=set_slug,
                set_name=set_name,
                set_price=set_lowest_price,
                part_cost=total_part_cost,
                profit_margin=profit_margin,
                profit_percentage=profit_percentage,
                part_details=part_details
            ))

    return profit_data


def calculate_profit_margins_dict(
    set_prices: List[Dict[str, Any]],
    part_prices: List[Dict[str, Any]],
    detailed_sets: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Calculate profit margins returning dictionaries for backwards compatibility.

    This version returns plain dicts instead of Pydantic models.
    """
    profit_data = []

    if not set_prices or not part_prices or not detailed_sets:
        return profit_data

    # Create lookup dictionaries for faster access
    set_price_lookup = {item['slug']: item for item in set_prices}
    part_price_lookup = {item['slug']: item for item in part_prices}

    for set_data in detailed_sets:
        set_slug = set_data.get('slug', '')
        set_name = set_data.get('name', 'Unknown Set')

        if not set_slug or set_slug not in set_price_lookup:
            continue

        set_price_data = set_price_lookup[set_slug]
        set_lowest_price = set_price_data['lowest_price']

        # Calculate total cost of individual parts
        total_part_cost = 0.0
        missing_parts = []
        part_details = []

        for part in set_data.get('setParts', []):
            part_code = part.get('code', '')
            part_name = part.get('name', 'Unknown Part')
            quantity_needed = part.get('quantityInSet', 1)

            if part_code in part_price_lookup:
                part_price_data = part_price_lookup[part_code]
                part_lowest_price = part_price_data['lowest_price']
                part_total_cost = part_lowest_price * quantity_needed
                total_part_cost += part_total_cost

                part_details.append({
                    'name': part_name,
                    'code': part_code,
                    'unit_price': part_lowest_price,
                    'quantity': quantity_needed,
                    'total_cost': part_total_cost
                })
            else:
                missing_parts.append(part_name)

        # Skip sets with missing part data
        if missing_parts:
            continue

        # Calculate profit margin
        if total_part_cost > 0:
            profit_margin = set_lowest_price - total_part_cost
            profit_percentage = (profit_margin / total_part_cost) * 100

            profit_data.append({
                'set_slug': set_slug,
                'set_name': set_name,
                'set_price': set_lowest_price,
                'part_cost': total_part_cost,
                'profit_margin': profit_margin,
                'profit_percentage': profit_percentage,
                'part_details': part_details
            })

    return profit_data
