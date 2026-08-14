"""RiskEngine — absolute veto authority over every trade.

All limits are read from :class:`Settings` (never hardcoded). The engine can
engage the master kill switch (EMERGENCY_STOP) via :class:`SystemState` when a
circuit-breaker threshold is breached.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from config.logging_config import get_logger
from config.settings import Settings, get_settings
from core.system_state import get_system_state

log = get_logger(__name__)


@dataclass
class PortfolioState:
    """Snapshot the risk engine evaluates against."""

    equity: float
    starting_equity_day: float
    starting_equity_week: float
    peak_equity: float
    open_positions: int = 0
    gross_exposure: float = 0.0             # sum |position notional|
    correlated_exposure: float = 0.0        # notional in the correlated cluster
    realized_pnl_day: float = 0.0
    realized_pnl_week: float = 0.0


@dataclass
class RiskDecision:
    allowed: bool
    reason: str = "ok"
    adjustments: Dict[str, Any] = field(default_factory=dict)
    checks: List[Dict[str, Any]] = field(default_factory=list)


class RiskEngine:
    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self.state = get_system_state()
        self._circuit_breaker_active = False

    # ------------------------------------------------------------------ #
    def check_trade(self, signal: Dict[str, Any], portfolio: PortfolioState) -> RiskDecision:
        """Evaluate a prospective trade against all risk limits.

        ``signal`` requires: symbol, direction, entry, stop, quantity, notional.
        """
        checks: List[Dict[str, Any]] = []
        s = self.settings

        if not self.state.is_trading_allowed():
            return RiskDecision(False, "trading_not_allowed", checks=checks)
        if self._circuit_breaker_active:
            return RiskDecision(False, "circuit_breaker_active", checks=checks)

        entry = float(signal.get("entry", 0) or 0)
        stop = float(signal.get("stop", 0) or 0)
        qty = float(signal.get("quantity", 0) or 0)
        notional = float(signal.get("notional", entry * qty))
        equity = portfolio.equity or 1e-9

        # 1. max risk per trade
        per_unit_risk = abs(entry - stop)
        trade_risk = per_unit_risk * qty
        trade_risk_pct = trade_risk / equity
        ok = trade_risk_pct <= s.MAX_RISK_PER_TRADE_PCT + 1e-9
        checks.append({"check": "max_risk_per_trade", "value": trade_risk_pct,
                       "limit": s.MAX_RISK_PER_TRADE_PCT, "passed": ok})
        if not ok:
            return RiskDecision(False, "exceeds_max_risk_per_trade", checks=checks)

        # 2. position size
        pos_pct = notional / equity
        ok = pos_pct <= s.MAX_POSITION_SIZE_PCT + 1e-9
        checks.append({"check": "max_position_size", "value": pos_pct,
                       "limit": s.MAX_POSITION_SIZE_PCT, "passed": ok})
        if not ok:
            return RiskDecision(False, "exceeds_max_position_size", checks=checks)

        # 3. simultaneous trades
        ok = portfolio.open_positions < s.MAX_SIMULTANEOUS_TRADES
        checks.append({"check": "max_simultaneous_trades", "value": portfolio.open_positions,
                       "limit": s.MAX_SIMULTANEOUS_TRADES, "passed": ok})
        if not ok:
            return RiskDecision(False, "exceeds_max_simultaneous_trades", checks=checks)

        # 4. leverage
        gross_after = portfolio.gross_exposure + notional
        leverage = gross_after / equity
        ok = leverage <= s.MAX_LEVERAGE + 1e-9
        checks.append({"check": "max_leverage", "value": leverage,
                       "limit": s.MAX_LEVERAGE, "passed": ok})
        if not ok:
            return RiskDecision(False, "exceeds_max_leverage", checks=checks)

        # 5. correlated exposure
        corr_pct = (portfolio.correlated_exposure + notional) / equity
        ok = corr_pct <= s.MAX_CORRELATED_EXPOSURE_PCT + 1e-9
        checks.append({"check": "max_correlated_exposure", "value": corr_pct,
                       "limit": s.MAX_CORRELATED_EXPOSURE_PCT, "passed": ok})
        if not ok:
            return RiskDecision(False, "exceeds_max_correlated_exposure", checks=checks)

        # 6. daily loss already breached?
        daily_loss_pct = self._loss_pct(portfolio.starting_equity_day, portfolio.equity)
        ok = daily_loss_pct <= s.MAX_DAILY_LOSS_PCT + 1e-9
        checks.append({"check": "max_daily_loss", "value": daily_loss_pct,
                       "limit": s.MAX_DAILY_LOSS_PCT, "passed": ok})
        if not ok:
            return RiskDecision(False, "daily_loss_limit_reached", checks=checks)

        # 7. weekly loss
        weekly_loss_pct = self._loss_pct(portfolio.starting_equity_week, portfolio.equity)
        ok = weekly_loss_pct <= s.MAX_WEEKLY_LOSS_PCT + 1e-9
        checks.append({"check": "max_weekly_loss", "value": weekly_loss_pct,
                       "limit": s.MAX_WEEKLY_LOSS_PCT, "passed": ok})
        if not ok:
            return RiskDecision(False, "weekly_loss_limit_reached", checks=checks)

        # 8. portfolio drawdown
        dd = self._loss_pct(portfolio.peak_equity, portfolio.equity)
        ok = dd <= s.MAX_PORTFOLIO_DRAWDOWN_PCT + 1e-9
        checks.append({"check": "max_portfolio_drawdown", "value": dd,
                       "limit": s.MAX_PORTFOLIO_DRAWDOWN_PCT, "passed": ok})
        if not ok:
            return RiskDecision(False, "portfolio_drawdown_limit_reached", checks=checks)

        return RiskDecision(True, "ok", checks=checks)

    # ------------------------------------------------------------------ #
    @staticmethod
    def _loss_pct(reference: float, current: float) -> float:
        if reference <= 0:
            return 0.0
        return max(0.0, (reference - current) / reference)

    def circuit_breaker_check(self, portfolio: PortfolioState) -> bool:
        """Trip the master kill switch if any hard loss threshold is breached.

        Returns True if the circuit breaker fired.
        """
        s = self.settings
        breaches: List[str] = []

        if self._loss_pct(portfolio.starting_equity_day, portfolio.equity) > s.MAX_DAILY_LOSS_PCT:
            breaches.append("daily_loss")
        if self._loss_pct(portfolio.starting_equity_week, portfolio.equity) > s.MAX_WEEKLY_LOSS_PCT:
            breaches.append("weekly_loss")
        if self._loss_pct(portfolio.peak_equity, portfolio.equity) > s.MAX_PORTFOLIO_DRAWDOWN_PCT:
            breaches.append("portfolio_drawdown")

        if breaches:
            self._circuit_breaker_active = True
            reason = f"circuit_breaker:{','.join(breaches)}"
            self.state.engage_emergency_stop(reason, actor="risk_engine")
            log.error("circuit_breaker_tripped", breaches=breaches)
            return True
        return False

    def is_circuit_breaker_active(self) -> bool:
        return self._circuit_breaker_active

    def reset_circuit_breaker(self) -> None:
        self._circuit_breaker_active = False

    def get_risk_summary(self, portfolio: PortfolioState) -> Dict[str, Any]:
        s = self.settings
        return {
            "mode": self.state.get_mode().value,
            "trading_allowed": self.state.is_trading_allowed(),
            "circuit_breaker_active": self._circuit_breaker_active,
            "daily_loss_pct": self._loss_pct(portfolio.starting_equity_day, portfolio.equity),
            "weekly_loss_pct": self._loss_pct(portfolio.starting_equity_week, portfolio.equity),
            "drawdown_pct": self._loss_pct(portfolio.peak_equity, portfolio.equity),
            "open_positions": portfolio.open_positions,
            "limits": {
                "max_risk_per_trade": s.MAX_RISK_PER_TRADE_PCT,
                "max_daily_loss": s.MAX_DAILY_LOSS_PCT,
                "max_weekly_loss": s.MAX_WEEKLY_LOSS_PCT,
                "max_portfolio_drawdown": s.MAX_PORTFOLIO_DRAWDOWN_PCT,
                "max_position_size": s.MAX_POSITION_SIZE_PCT,
                "max_leverage": s.MAX_LEVERAGE,
                "max_simultaneous_trades": s.MAX_SIMULTANEOUS_TRADES,
                "max_correlated_exposure": s.MAX_CORRELATED_EXPOSURE_PCT,
            },
        }
