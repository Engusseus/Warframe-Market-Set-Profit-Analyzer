"""Sets API routes."""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ...db.database import get_database_instance
from ...models.schemas import SetDetailResponse, SetHistoryEntry, SetsListResponse

router = APIRouter()


@router.get("", response_model=SetsListResponse)
async def get_sets(
    sort_by: str = Query("name", description="Sort field: name, profit, price"),
    order: str = Query("asc", description="Sort order: asc or desc")
) -> SetsListResponse:
    """Get all Prime sets from database."""
    db = await get_database_instance()

    try:
        sets = await db.get_all_sets()

        # Sort sets
        reverse = order.lower() == "desc"
        if sort_by == "name":
            sets.sort(key=lambda x: x.get('name', ''), reverse=reverse)
        elif sort_by == "slug":
            sets.sort(key=lambda x: x.get('slug', ''), reverse=reverse)

        return SetsListResponse(
            sets=sets,
            total_sets=len(sets),
            sort_by=sort_by,
            order=order
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{slug}", response_model=SetDetailResponse)
async def get_set_detail(slug: str) -> SetDetailResponse:
    """Get detailed information for a specific set."""
    db = await get_database_instance()

    try:
        # Get price history for this set
        history = await db.get_set_price_history(slug, limit=1)

        if not history:
            raise HTTPException(status_code=404, detail="Set not found")

        # Get latest data point
        latest = history[0] if history else {}

        # Get full history
        full_history = await db.get_set_price_history(slug, limit=50)

        history_entries = [
            SetHistoryEntry(
                date_string=h['date_string'],
                timestamp=h['timestamp'],
                profit_margin=h['profit_margin'],
                lowest_price=h['lowest_price']
            )
            for h in full_history
        ]

        return SetDetailResponse(
            slug=slug,
            name=slug.replace('_', ' ').title().replace(' Prime Set', ' Prime Set'),
            current_price=latest.get('lowest_price'),
            current_profit=latest.get('profit_margin'),
            parts=[],  # Parts not stored in DB, would need cache lookup
            history=history_entries
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{slug}/history")
async def get_set_history(
    slug: str,
    days: int = Query(30, ge=1, le=365, description="Number of days")
):
    """Get price and profit history for a set."""
    db = await get_database_instance()

    try:
        trends = await db.get_profit_trends(slug, days=days)

        if not trends:
            raise HTTPException(status_code=404, detail="Set not found or no history")

        return {
            "slug": slug,
            "days": days,
            "data_points": len(trends),
            "history": trends
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
