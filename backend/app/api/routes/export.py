"""Export API routes."""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse

from ...db.database import get_database_instance
from ...models.schemas import ExportResponse

router = APIRouter()


@router.get("")
async def export_data(
    format: str = Query("json", description="Export format: json"),
    include_history: bool = Query(True, description="Include full history")
):
    """Export all market data."""
    db = await get_database_instance()

    try:
        if format.lower() != "json":
            raise HTTPException(
                status_code=400,
                detail="Only JSON format is currently supported"
            )

        # Get export data
        export_data = await db.export_to_json()

        return JSONResponse(content=export_data)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/file")
async def export_to_file():
    """Export data to a downloadable JSON file."""
    db = await get_database_instance()

    try:
        # Save to file
        output_path = await db.save_json_export()

        return FileResponse(
            path=output_path,
            filename="market_data_export.json",
            media_type="application/json"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
async def export_summary():
    """Get a quick summary of exportable data."""
    db = await get_database_instance()

    try:
        stats = await db.get_database_stats()

        return {
            "total_runs": stats['total_runs'],
            "total_records": stats['total_profit_records'],
            "database_size_bytes": stats['database_size_bytes'],
            "first_run": stats.get('first_run'),
            "last_run": stats.get('last_run'),
            "export_available": stats['total_runs'] > 0
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
