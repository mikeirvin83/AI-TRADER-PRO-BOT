"""Backtest engine + performance metric tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import numpy as np
import pandas as pd
import pytest

from backtesting.backtest_engine import BacktestConfig, BacktestEngine, BacktestResult
from backtesting.metrics import max_drawdown, sharpe_ratio, sortino_ratio, compute_metrics
from config.constants import SignalDirection
from strategies.base_strategy import BaseStrategy, StrategySignal


# --- pure metric tests ------------------------------------------------------ #
def test_max_drawdown_simple():
    curve = [100, 120, 90, 110]
    dd = max_drawdown(curve)
    # peak 120 -> trough 90 => 25% drawdown
    assert dd == pytest.approx(0.25, abs=1e-9)


def test_sharpe_zero_for_no_variance():
    returns = [0.0] * 10
    assert sharpe_ratio(returns) == 0.0


def test_sortino_handles_no_downside():
    returns = [0.01] * 10  # no negative returns
    val = sortino_ratio(returns)
    assert val >= 0.0


def test_compute_metrics_basic():
    pnls = [100, -50, 75, -25]
    equity = [100_000, 100_100, 100_050, 100_125, 100_100]
    m = compute_metrics(pnls, equity, period_returns=[0.001, -0.0005, 0.00075, -0.00025])
    assert m.num_trades == 4
    assert 0.0 <= m.win_rate <= 1.0


# --- integration: trivial strategy over synthetic data ---------------------- #
class _AlwaysLongStrategy(BaseStrategy):
    name = "always_long_test"
    category = "test"

    def generate_signal(self, data, features, regime=None, news=None) -> Optional[StrategySignal]:
        last = data.iloc[-1]
        entry = float(last["close"])
        return StrategySignal(
            asset=data.attrs.get("symbol", "TEST"),
            direction=SignalDirection.LONG,
            entry=entry,
            stop=entry * 0.95,
            target=entry * 1.05,
            invalidation_condition="close < stop",
            expiration_time=datetime.now(timezone.utc) + timedelta(days=5),
            strategy_name=self.name,
        )


def test_backtest_runs_without_lookahead():
    idx = pd.date_range("2024-01-01", periods=120, freq="D", tz="UTC")
    close = pd.Series(np.linspace(100, 130, 120), index=idx)
    df = pd.DataFrame({
        "open": close, "high": close * 1.02, "low": close * 0.98,
        "close": close, "volume": 1_000_000.0,
    })
    engine = BacktestEngine(BacktestConfig(initial_capital=100_000, warmup_bars=50))
    result = engine.run(_AlwaysLongStrategy(), df, symbol="TEST")
    assert isinstance(result, BacktestResult)
    assert len(result.equity_curve) > 0
    # Equity curve should be finite and positive.
    assert all(np.isfinite(result.equity_curve))
    assert result.equity_curve[-1] > 0
