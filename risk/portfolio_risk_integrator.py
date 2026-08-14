"""Portfolio-level risk integration.

Feeds real-time portfolio state into the risk engine, tracks P&L watermarks,
and manages the daily/weekly/peak equity references that circuit breakers
evaluate against.
"""
from __future__ import annotations

from datetime import datetime, date, timezone
from typing import Any, Dict, List, Optional

from config.logging_config import get_logger
from risk.risk_engine import PortfolioState, RiskEngine

log = get_logger(__name__)


class PortfolioRiskIntegrator:
    """Maintains the live PortfolioState and feeds it to the RiskEngine.

    Call :meth:`update` whenever equity or positions change. The integrator
    tracks daily/weekly start equity automatically by checking the date.
    """

    def __init__(self, initial_equity: float = 100_000.0,
                 risk_engine: Optional[RiskEngine] = None) -> None:
        self.risk_engine = risk_engine or RiskEngine()
        self._portfolio = PortfolioState(
            equity=initial_equity,
            starting_equity_day=initial_equity,
            starting_equity_week=initial_equity,
            peak_equity=initial_equity,
        )
        self._last_day: Optional[date] = None
        self._last_week_start: Optional[date] = None
        self._daily_pnl_history: List[float] = []
        self._equity_history: List[float] = [initial_equity]

    @property
    def portfolio(self) -> PortfolioState:
        return self._portfolio

    def update(
        self,
        equity: float,
        open_positions: int = 0,
        gross_exposure: float = 0.0,
        correlated_exposure: float = 0.0,
        realized_pnl_today: float = 0.0,
        realized_pnl_week: float = 0.0,
    ) -> PortfolioState:
        """Update the live portfolio state."""
        now = datetime.now(timezone.utc)
        today = now.date()

        # Roll daily reference at the start of a new day
        if self._last_day is not None and today != self._last_day:
            daily_pnl = self._portfolio.equity - self._portfolio.starting_equity_day
            self._daily_pnl_history.append(daily_pnl)
            self._portfolio.starting_equity_day = self._portfolio.equity
            log.info("daily_equity_rolled", new_day=today.isoformat(),
                     start_equity=round(self._portfolio.starting_equity_day, 2))

        # Roll weekly reference (Monday)
        if self._last_week_start is None or (
            today.weekday() == 0 and today != self._last_week_start
        ):
            self._portfolio.starting_equity_week = self._portfolio.equity
            self._last_week_start = today

        self._last_day = today
        self._portfolio.equity = equity
        self._portfolio.open_positions = open_positions
        self._portfolio.gross_exposure = gross_exposure
        self._portfolio.correlated_exposure = correlated_exposure
        self._portfolio.realized_pnl_day = realized_pnl_today
        self._portfolio.realized_pnl_week = realized_pnl_week

        # Update peak
        if equity > self._portfolio.peak_equity:
            self._portfolio.peak_equity = equity

        self._equity_history.append(equity)
        return self._portfolio

    def check_circuit_breakers(self) -> bool:
        """Run the risk engine circuit breaker check against current state."""
        return self.risk_engine.circuit_breaker_check(self._portfolio)

    def get_drawdown(self) -> float:
        peak = self._portfolio.peak_equity
        if peak <= 0:
            return 0.0
        return max(0.0, (peak - self._portfolio.equity) / peak)

    def get_risk_summary(self) -> Dict[str, Any]:
        summary = self.risk_engine.get_risk_summary(self._portfolio)
        summary["drawdown_pct"] = round(self.get_drawdown(), 4)
        summary["daily_pnl_history"] = self._daily_pnl_history[-30:]
        return summary

    def snapshot(self) -> Dict[str, Any]:
        p = self._portfolio
        return {
            "equity": round(p.equity, 2),
            "starting_equity_day": round(p.starting_equity_day, 2),
            "starting_equity_week": round(p.starting_equity_week, 2),
            "peak_equity": round(p.peak_equity, 2),
            "drawdown_pct": round(self.get_drawdown(), 4),
            "open_positions": p.open_positions,
            "gross_exposure": round(p.gross_exposure, 2),
            "correlated_exposure": round(p.correlated_exposure, 2),
        }
