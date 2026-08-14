"""Risk router."""
from __future__ import annotations

from fastapi import APIRouter

from api.schemas import RiskSummaryResponse
from risk.risk_engine import PortfolioState, RiskEngine

router = APIRouter(prefix="/risk", tags=["risk"])


@router.get("/summary", response_model=RiskSummaryResponse)
def risk_summary() -> RiskSummaryResponse:
    engine = RiskEngine()
    # Neutral portfolio snapshot when no live equity is wired in yet.
    portfolio = PortfolioState(
        equity=100_000, starting_equity_day=100_000,
        starting_equity_week=100_000, peak_equity=100_000,
    )
    summary = engine.get_risk_summary(portfolio)
    return RiskSummaryResponse(**summary)
