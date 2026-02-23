"""Pydantic models for request/response schemas."""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# === Enums ===

class StrategyType(str, Enum):
    """Available trading strategy types."""
    SAFE_STEADY = "safe_steady"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"


class RiskLevel(str, Enum):
    """Risk level classification."""
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class TrendDirection(str, Enum):
    """Trend direction classification."""
    RISING = "rising"
    FALLING = "falling"
    STABLE = "stable"


class ExecutionMode(str, Enum):
    """Execution assumptions for profit and scoring calculations."""
    INSTANT = "instant"
    PATIENT = "patient"


# === Part and Set Data Models ===

class OrderbookLevel(BaseModel):
    """Price level from market orderbook."""
    platinum: float
    quantity: int = 1


class PartDetail(BaseModel):
    """Individual part information within a set."""
    name: str
    code: str
    unit_price: float
    quantity: int
    total_cost: float
    lowest_price: Optional[float] = None
    highest_bid: Optional[float] = None
    top_sell_orders: List[OrderbookLevel] = Field(default_factory=list)
    top_buy_orders: List[OrderbookLevel] = Field(default_factory=list)
    instant_unit_price: Optional[float] = None
    patient_unit_price: Optional[float] = None
    instant_total_cost: Optional[float] = None
    patient_total_cost: Optional[float] = None


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
    highest_bid: float = 0.0
    price_count: int
    min_price: float
    max_price: float
    top_sell_orders: List[OrderbookLevel] = Field(default_factory=list)
    top_buy_orders: List[OrderbookLevel] = Field(default_factory=list)
    id: Optional[str] = None


class PartPriceData(BaseModel):
    """Pricing data for an individual part."""
    slug: str
    name: str
    lowest_price: float
    highest_bid: float = 0.0
    price_count: int
    min_price: float
    max_price: float
    top_sell_orders: List[OrderbookLevel] = Field(default_factory=list)
    top_buy_orders: List[OrderbookLevel] = Field(default_factory=list)
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
    instant_set_price: Optional[float] = None
    instant_part_cost: Optional[float] = None
    instant_profit_margin: Optional[float] = None
    instant_profit_percentage: Optional[float] = None
    patient_set_price: Optional[float] = None
    patient_part_cost: Optional[float] = None
    patient_profit_margin: Optional[float] = None
    patient_profit_percentage: Optional[float] = None
    part_details: List[PartDetail]


class ScoredData(ProfitData):
    """Scored profit data with normalized values and trend/volatility metrics."""
    execution_mode: ExecutionMode = ExecutionMode.INSTANT
    volume: int = 0
    normalized_profit: float = 0.0
    normalized_volume: float = 0.0
    profit_score: float = 0.0
    volume_score: float = 0.0
    total_score: float = 0.0
    # Trend analysis fields
    trend_slope: float = 0.0
    trend_multiplier: float = 1.0
    trend_direction: str = "stable"
    # Volatility/risk fields
    volatility: float = 0.0
    volatility_penalty: float = 1.0
    risk_level: str = "Medium"
    # Composite score (multiplicative formula)
    composite_score: float = 0.0
    # Score breakdown for UI display
    profit_contribution: float = 0.0
    volume_contribution: float = 0.0
    trend_contribution: float = 1.0
    volatility_contribution: float = 1.0
    # Liquidity velocity fields
    bid_ask_ratio: float = 0.0
    sell_side_competition: float = 0.0
    liquidity_velocity: float = 0.0
    liquidity_multiplier: float = 1.0


# === API Request/Response Models ===

class AnalysisConfig(BaseModel):
    """Configuration for running analysis."""
    strategy: StrategyType = StrategyType.BALANCED
    execution_mode: ExecutionMode = ExecutionMode.INSTANT
    force_refresh: bool = False
    # Legacy fields for backward compatibility
    profit_weight: float = Field(default=1.0, ge=0.0, le=10.0)
    volume_weight: float = Field(default=1.2, ge=0.0, le=10.0)


class WeightsConfig(BaseModel):
    """Scoring weights configuration."""
    strategy: StrategyType = StrategyType.BALANCED
    # Legacy fields for backward compatibility
    profit_weight: float = 1.0
    volume_weight: float = 1.2


class StrategyProfileResponse(BaseModel):
    """Strategy profile information."""
    type: StrategyType
    name: str
    description: str
    volatility_weight: float
    trend_weight: float
    roi_weight: float
    min_volume_threshold: int


class AnalysisResponse(BaseModel):
    """Response for analysis endpoints."""
    run_id: Optional[int] = None
    timestamp: datetime
    sets: List[ScoredData]
    total_sets: int
    profitable_sets: int
    weights: WeightsConfig
    strategy: StrategyType = StrategyType.BALANCED
    execution_mode: ExecutionMode = ExecutionMode.INSTANT
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
