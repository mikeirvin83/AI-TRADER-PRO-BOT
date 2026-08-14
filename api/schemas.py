"""Pydantic response/request schemas for the API layer."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from config.settings import TradingMode


class HealthResponse(BaseModel):
    status: str = "ok"
    mode: str
    trading_allowed: bool
    version: str = "0.1.0"


class AccountResponse(BaseModel):
    equity: float
    cash: float
    buying_power: Optional[float] = None
    mode: str


class PositionResponse(BaseModel):
    symbol: str
    qty: float
    avg_entry_price: float
    market_value: Optional[float] = None
    unrealized_pnl: Optional[float] = None


class StrategyResponse(BaseModel):
    name: str
    category: str
    status: str
    version: str
    allowed_regimes: List[str] = Field(default_factory=list)
    min_signal_score: int


class SignalResponse(BaseModel):
    symbol: str
    direction: str
    entry: float
    stop: float
    target: float
    score: float
    regime: Optional[str] = None
    expiration_time: datetime


class RiskSummaryResponse(BaseModel):
    mode: str
    trading_allowed: bool
    circuit_breaker_active: bool
    daily_loss_pct: float
    weekly_loss_pct: float
    drawdown_pct: float
    open_positions: int
    limits: Dict[str, Any]


class ModeChangeRequest(BaseModel):
    mode: TradingMode
    reason: str = "manual"
    actor: str = "api"


class KillSwitchRequest(BaseModel):
    reason: str = "manual_kill_switch"
    actor: str = "api"


class ModeResponse(BaseModel):
    mode: str
    trading_allowed: bool
    emergency_stopped: bool


class HypothesisRequest(BaseModel):
    title: str
    description: str = ""
    rationale: str = ""
    success_criteria: Dict[str, Any] = Field(default_factory=dict)


class GenericResponse(BaseModel):
    success: bool
    detail: str = ""
    data: Dict[str, Any] = Field(default_factory=dict)
