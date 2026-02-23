"""ROI utilities shared across scoring modules."""


def calculate_sign_preserving_roi_factor(
    base_score: float,
    roi: float,
    weight: float = 1.0,
) -> float:
    """Calculate a sign-preserving ROI factor for multiplicative scoring.

    For positive base scores, positive ROI increases score magnitude and negative ROI
    decreases it. For negative base scores, the behavior is mirrored so negative ROI
    increases negative magnitude (more negative) instead of collapsing toward zero.

    Args:
        base_score: Base score before ROI adjustment.
        roi: ROI percentage (for example, 50.0 for +50%).
        weight: Optional scaling factor for strategy-specific ROI emphasis.

    Returns:
        Positive ROI multiplier with a floor to avoid score collapse to zero.
    """
    if base_score == 0 or roi == 0 or weight == 0:
        return 1.0

    signed_weighted_roi = (roi / 100.0) * weight
    direction = 1.0 if base_score > 0 else -1.0
    factor = 1.0 + (direction * signed_weighted_roi)

    # Prevent ROI from flipping score direction through a negative multiplier,
    # and keep a small floor so scores do not collapse to zero.
    return max(0.1, factor)
