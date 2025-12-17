"""Data normalization utilities.

Extracted from main.py lines 837-862.
"""
from typing import List, Optional


def normalize_data(
    values: List[float],
    min_val: Optional[float] = None,
    max_val: Optional[float] = None
) -> List[float]:
    """Normalize a list of values to 0-1 range using min-max scaling.

    Args:
        values: List of numeric values to normalize
        min_val: Optional minimum value override
        max_val: Optional maximum value override

    Returns:
        List of normalized values in range [0, 1]

    Note:
        When all values are the same (max == min), returns zeros
        to avoid artificial boosting in scoring algorithms.
    """
    if not values:
        return []

    if min_val is None:
        min_val = min(values)
    if max_val is None:
        max_val = max(values)

    # Handle case where all values are the same
    if max_val == min_val:
        # Return zeros instead of 0.5 to avoid artificial boosting
        return [0.0] * len(values)

    range_val = max_val - min_val
    return [(value - min_val) / range_val for value in values]
