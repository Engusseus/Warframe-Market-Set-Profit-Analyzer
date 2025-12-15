"""Pydantic models for request/response schemas."""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# === Part and Set Data Models ===

class PartDetail(BaseModel):
    """Individual part information within a set."""
    name: str
    code: str
    unit_price: float
    quantity: int
    total_cost: float


class PartQuantity(BaseModel):
    """Part quantity information from API."""
    code: str
    name: str
    quantity_in_set: int = Field(alias="quantityInSet", default=1)

    class Config:
        populate_by_name = True


class SetPriceData(BaseModel):
    """Pricing data for a complete set."""
    slug: str
    name: str
    lowest_price: float
    price_count: int
    min_price: float
    max_price: float
    id: Optional[str] = None


class PartPriceData(BaseModel):
    """Pricing data for an individual part."""
    slug: str
    name: str
    lowest_price: float
    price_count: int
    min_price: float
    max_price: float
    quantity_in_set: int = 1


class DetailedSet(BaseModel):
    """Detailed set information with parts."""
    id: str
    name: str
    slug: str
    set_parts: List[Dict[str, Any]] = Field(alias="setParts", default_factory=list)

    class Config:
        populate_by_name = True


# === Profit Analysis Models ===

class ProfitData(BaseModel):
    """Profit analysis result for a set."""
    set_slug: str
    set_name: str
    set_price: float
    part_cost: float
    profit_margin: float
    profit_percentage: float
    part_details: List[PartDetail]


class ScoredData(ProfitData):
    """Scored profit data with normalized values."""
    volume: int = 0
    normalized_profit: float = 0.0
    normalized_volume: float = 0.0
    profit_score: float = 0.0
    volume_score: float = 0.0
    total_score: float = 0.0


# === API Request/Response Models ===

class AnalysisConfig(BaseModel):
    """Configuration for running analysis."""
    profit_weight: float = Field(default=1.0, ge=0.0, le=10.0)
    volume_weight: float = Field(default=1.2, ge=0.0, le=10.0)
    force_refresh: bool = False


class WeightsConfig(BaseModel):
    """Scoring weights configuration."""
    profit_weight: float = 1.0
    volume_weight: float = 1.2


class AnalysisResponse(BaseModel):
    """Response for analysis endpoints."""
    run_id: Optional[int] = None
    timestamp: datetime
    sets: List[ScoredData]
    total_sets: int
    profitable_sets: int
    weights: WeightsConfig
    cached: bool = False


class AnalysisStartedResponse(BaseModel):
    """Response when analysis is started in background."""
    message: str
    status: str = "started"
    estimated_time_seconds: int = 60


class AnalysisStatusResponse(BaseModel):
    """Response for analysis status check."""
    status: str  # "idle", "running", "completed", "error"
    progress: Optional[int] = None  # Percentage 0-100
    message: Optional[str] = None
    run_id: Optional[int] = None


# === History Models ===

class HistoryRun(BaseModel):
    """Summary of a historical market run."""
    run_id: int
    date_string: str
    set_count: int
    avg_profit: Optional[float] = None
    max_profit: Optional[float] = None


class HistoryResponse(BaseModel):
    """Response for history list endpoint."""
    runs: List[HistoryRun]
    total_runs: int
    page: int = 1
    page_size: int = 10


class RunDetailResponse(BaseModel):
    """Detailed data for a specific run."""
    run_id: int
    date_string: str
    timestamp: int
    sets: List[Dict[str, Any]]
    summary: Dict[str, Any]


# === Set Detail Models ===

class SetHistoryEntry(BaseModel):
    """Historical entry for a set."""
    date_string: str
    timestamp: int
    profit_margin: float
    lowest_price: float


class SetDetailResponse(BaseModel):
    """Detailed information for a specific set."""
    slug: str
    name: str
    current_price: Optional[float] = None
    current_profit: Optional[float] = None
    parts: List[PartDetail] = []
    history: List[SetHistoryEntry] = []


class SetsListResponse(BaseModel):
    """Response for sets list endpoint."""
    sets: List[Dict[str, Any]]
    total_sets: int
    sort_by: str = "score"
    order: str = "desc"


# === Statistics Models ===

class DatabaseStats(BaseModel):
    """Database statistics."""
    total_runs: int
    total_profit_records: int
    database_size_bytes: int
    first_run: Optional[str] = None
    last_run: Optional[str] = None
    time_span_days: Optional[float] = None


class AnalysisStats(BaseModel):
    """Analysis-related statistics."""
    cache_age_seconds: Optional[float] = None
    last_analysis: Optional[str] = None
    total_prime_sets: Optional[int] = None


class StatsResponse(BaseModel):
    """Combined statistics response."""
    database: DatabaseStats
    analysis: AnalysisStats


# === Export Models ===

class ExportMetadata(BaseModel):
    """Metadata for data export."""
    export_timestamp: int
    export_date: str
    total_runs: int
    database_path: str


class ExportResponse(BaseModel):
    """Response for export endpoint."""
    metadata: ExportMetadata
    market_runs: List[Dict[str, Any]]


# === Error Models ===

class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: Optional[str] = None
    status_code: int = 500


class ValidationErrorResponse(BaseModel):
    """Validation error response."""
    error: str = "Validation Error"
    details: List[Dict[str, Any]]
    status_code: int = 422
