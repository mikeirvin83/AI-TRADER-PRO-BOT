"""Strategy Benchmarking — compare against passive benchmarks (Section 44).

A strategy is not considered successful merely because it makes money.
It must demonstrate meaningful risk-adjusted improvement over simple
passive alternatives.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from backtesting.metrics import PerformanceMetrics, compute_metrics, max_drawdown
from config.logging_config import get_logger

log = get_logger(__name__)


@dataclass
class BenchmarkResult:
    benchmark_name: str
    metrics: PerformanceMetrics
    excess_return: float = 0.0        # strategy return - benchmark return
    excess_sharpe: float = 0.0        # strategy Sharpe - benchmark Sharpe
    information_ratio: float = 0.0    # excess return / tracking error
    outperforms: bool = False


def _buy_and_hold_returns(prices: pd.Series) -> List[float]:
    """Simple buy-and-hold period returns from a price series."""
    returns = prices.pct_change().dropna().tolist()
    return returns


def _simple_momentum_returns(prices: pd.Series, lookback: int = 20) -> List[float]:
    """Long when price > SMA(lookback), flat otherwise."""
    sma = prices.rolling(lookback).mean()
    position = (prices > sma).astype(float)
    raw_returns = prices.pct_change()
    strat_returns = (position.shift(1) * raw_returns).dropna().tolist()
    return strat_returns


def _risk_free_returns(n_periods: int, annual_rate: float = 0.04,
                       periods_per_year: int = 252) -> List[float]:
    """Constant risk-free return per period."""
    per_period = (1 + annual_rate) ** (1 / periods_per_year) - 1
    return [per_period] * n_periods


class StrategyBenchmarker:
    """Compare a strategy's returns against multiple passive benchmarks."""

    def __init__(self, risk_free_rate: float = 0.04) -> None:
        self.risk_free_rate = risk_free_rate

    def compare(
        self,
        strategy_returns: Sequence[float],
        benchmark_prices: Optional[pd.Series] = None,
        benchmark_name: str = "SPY",
    ) -> List[BenchmarkResult]:
        """Compare strategy against buy-and-hold, simple momentum, and risk-free.

        Args:
            strategy_returns: Per-period fractional returns of the strategy.
            benchmark_prices: Price series for the passive benchmark (e.g. SPY).
            benchmark_name: Label for the benchmark.

        Returns:
            List of BenchmarkResult, one per benchmark variant.
        """
        results: List[BenchmarkResult] = []
        s_arr = np.array(strategy_returns, dtype=float)
        n = len(s_arr)
        if n < 2:
            return results

        s_equity = np.cumprod(1 + s_arr).tolist()
        s_metrics = compute_metrics([], s_equity, strategy_returns)

        # 1. Buy-and-hold
        if benchmark_prices is not None and len(benchmark_prices) >= n:
            bh_rets = _buy_and_hold_returns(benchmark_prices.iloc[-n - 1:])
            bh_rets = bh_rets[:n]
            if bh_rets:
                bh_eq = np.cumprod(1 + np.array(bh_rets)).tolist()
                bh_m = compute_metrics([], bh_eq, bh_rets)
                results.append(self._build_result(
                    f"{benchmark_name}_buy_hold", s_metrics, bh_m, s_arr, np.array(bh_rets)))

            # 2. Simple momentum
            mom_rets = _simple_momentum_returns(benchmark_prices.iloc[-n - 21:])[-n:]
            if mom_rets:
                mom_eq = np.cumprod(1 + np.array(mom_rets)).tolist()
                mom_m = compute_metrics([], mom_eq, mom_rets)
                results.append(self._build_result(
                    f"{benchmark_name}_momentum", s_metrics, mom_m, s_arr, np.array(mom_rets)))

        # 3. Risk-free
        rf_rets = _risk_free_returns(n, self.risk_free_rate)
        rf_eq = np.cumprod(1 + np.array(rf_rets)).tolist()
        rf_m = compute_metrics([], rf_eq, rf_rets)
        results.append(self._build_result(
            "risk_free", s_metrics, rf_m, s_arr, np.array(rf_rets)))

        return results

    def _build_result(
        self, name: str, s_m: PerformanceMetrics, b_m: PerformanceMetrics,
        s_rets: np.ndarray, b_rets: np.ndarray,
    ) -> BenchmarkResult:
        excess_return = s_m.total_return - b_m.total_return
        excess_sharpe = s_m.sharpe - b_m.sharpe
        tracking_error = float(np.std(s_rets - b_rets, ddof=1)) if len(s_rets) > 1 else 1e-9
        ir = float(np.mean(s_rets - b_rets) / tracking_error) if tracking_error > 0 else 0
        outperforms = excess_sharpe > 0 and excess_return > 0
        return BenchmarkResult(name, b_m, excess_return, excess_sharpe, ir, outperforms)

    def summary(self, results: List[BenchmarkResult]) -> Dict[str, Any]:
        return {
            "benchmarks": [
                {
                    "name": r.benchmark_name,
                    "excess_return": round(r.excess_return, 4),
                    "excess_sharpe": round(r.excess_sharpe, 4),
                    "information_ratio": round(r.information_ratio, 4),
                    "outperforms": r.outperforms,
                }
                for r in results
            ],
            "outperforms_all": all(r.outperforms for r in results),
        }
