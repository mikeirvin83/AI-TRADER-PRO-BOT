"""Performance metrics computed from a trade list and/or an equity curve."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import List, Sequence

import numpy as np

from config.constants import TRADING_DAYS_PER_YEAR
from config.settings import get_settings


@dataclass
class PerformanceMetrics:
    total_return: float = 0.0
    cagr: float = 0.0
    sharpe: float = 0.0
    sortino: float = 0.0
    max_drawdown: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    num_trades: int = 0
    exposure_time: float = 0.0
    recovery_factor: float = 0.0
    annual_volatility: float = 0.0
    cvar_5: float = 0.0  # expected shortfall (tail loss), 5% level

    def to_dict(self) -> dict:
        return asdict(self)


def max_drawdown(equity_curve: Sequence[float]) -> float:
    if len(equity_curve) == 0:
        return 0.0
    arr = np.asarray(equity_curve, dtype=float)
    peaks = np.maximum.accumulate(arr)
    dd = (peaks - arr) / np.where(peaks == 0, np.nan, peaks)
    return float(np.nanmax(dd)) if len(dd) else 0.0


def sharpe_ratio(returns: Sequence[float], risk_free: float | None = None,
                 periods_per_year: int = TRADING_DAYS_PER_YEAR) -> float:
    r = np.asarray(returns, dtype=float)
    if r.size < 2:
        return 0.0
    rf = (risk_free if risk_free is not None else get_settings().RISK_FREE_RATE) / periods_per_year
    excess = r - rf
    sd = excess.std(ddof=1)
    if sd == 0:
        return 0.0
    return float(np.sqrt(periods_per_year) * excess.mean() / sd)


def sortino_ratio(returns: Sequence[float], risk_free: float | None = None,
                  periods_per_year: int = TRADING_DAYS_PER_YEAR) -> float:
    r = np.asarray(returns, dtype=float)
    if r.size < 2:
        return 0.0
    rf = (risk_free if risk_free is not None else get_settings().RISK_FREE_RATE) / periods_per_year
    excess = r - rf
    downside = excess[excess < 0]
    dd = np.sqrt((downside ** 2).mean()) if downside.size else 0.0
    if dd == 0:
        return 0.0
    return float(np.sqrt(periods_per_year) * excess.mean() / dd)


def cvar(returns: Sequence[float], level: float = 0.05) -> float:
    r = np.asarray(returns, dtype=float)
    if r.size == 0:
        return 0.0
    var = np.quantile(r, level)
    tail = r[r <= var]
    return float(tail.mean()) if tail.size else float(var)


def compute_metrics(
    trade_pnls: Sequence[float],
    equity_curve: Sequence[float],
    period_returns: Sequence[float] | None = None,
    n_periods: int | None = None,
    exposure_time: float = 0.0,
) -> PerformanceMetrics:
    """Compute the full metrics suite.

    ``trade_pnls``    : per-trade P&L (currency).
    ``equity_curve``  : equity value per step.
    ``period_returns``: per-period fractional returns (for Sharpe/Sortino).
    """
    m = PerformanceMetrics()
    pnls = np.asarray(trade_pnls, dtype=float)
    m.num_trades = int(pnls.size)

    if len(equity_curve) >= 2:
        start, end = equity_curve[0], equity_curve[-1]
        if start > 0:
            m.total_return = float(end / start - 1.0)
            periods = n_periods or len(equity_curve)
            years = max(periods / TRADING_DAYS_PER_YEAR, 1e-9)
            m.cagr = float((end / start) ** (1.0 / years) - 1.0) if end > 0 else -1.0
    m.max_drawdown = max_drawdown(equity_curve)

    if pnls.size:
        wins = pnls[pnls > 0]
        losses = pnls[pnls < 0]
        m.win_rate = float(wins.size / pnls.size)
        m.avg_win = float(wins.mean()) if wins.size else 0.0
        m.avg_loss = float(losses.mean()) if losses.size else 0.0
        gross_profit = float(wins.sum())
        gross_loss = float(-losses.sum())
        m.profit_factor = float(gross_profit / gross_loss) if gross_loss > 0 else float("inf") if gross_profit > 0 else 0.0
        m.expectancy = float(pnls.mean())

    if period_returns is not None and len(period_returns) >= 2:
        pr = np.asarray(period_returns, dtype=float)
        m.sharpe = sharpe_ratio(pr)
        m.sortino = sortino_ratio(pr)
        m.annual_volatility = float(pr.std(ddof=1) * np.sqrt(TRADING_DAYS_PER_YEAR))
        m.cvar_5 = cvar(pr, 0.05)

    m.exposure_time = float(exposure_time)
    if m.max_drawdown > 0:
        m.recovery_factor = float(abs(m.total_return) / m.max_drawdown)
    return m
