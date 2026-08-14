"""Indicator correctness tests using hand-verifiable inputs."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from features import trend, momentum, volatility


def _series(vals):
    return pd.Series(vals, dtype=float)


def test_sma_basic():
    s = _series([1, 2, 3, 4, 5])
    out = trend.sma(s, period=3)
    # Last window mean = (3+4+5)/3 = 4
    assert out.iloc[-1] == pytest.approx(4.0)
    # First two are NaN (min_periods)
    assert np.isnan(out.iloc[0]) and np.isnan(out.iloc[1])


def test_ema_first_value_equals_seed():
    s = _series(range(1, 21))
    out = trend.ema(s, period=5)
    # EMA is monotonic increasing for a monotonic increasing series
    valid = out.dropna()
    assert valid.is_monotonic_increasing
    assert valid.iloc[-1] < s.iloc[-1]  # EMA lags the raw series


def test_rsi_all_gains_is_100():
    s = _series(range(1, 40))  # strictly increasing => no losses
    out = momentum.rsi(s, period=14)
    assert out.dropna().iloc[-1] == pytest.approx(100.0)


def test_rsi_range_bounded():
    rng = np.random.default_rng(42)
    s = _series(100 + np.cumsum(rng.normal(0, 1, 200)))
    out = momentum.rsi(s, period=14).dropna()
    assert (out >= 0).all() and (out <= 100).all()


def test_atr_positive_and_reasonable():
    idx = pd.date_range("2024-01-01", periods=30, freq="D")
    close = pd.Series(np.linspace(100, 110, 30), index=idx)
    df = pd.DataFrame({
        "open": close, "high": close + 1.0, "low": close - 1.0,
        "close": close, "volume": 1000.0,
    })
    atr = volatility.atr(df, period=14).dropna()
    assert (atr > 0).all()
    # Range is ~2 per bar; ATR should be near 2.
    assert atr.iloc[-1] == pytest.approx(2.0, abs=0.6)


def test_bollinger_bands_ordering():
    rng = np.random.default_rng(7)
    s = _series(100 + np.cumsum(rng.normal(0, 1, 100)))
    bb = volatility.bollinger_bands(s, period=20, num_std=2.0).dropna()
    assert (bb["bb_upper"] >= bb["bb_mid"]).all()
    assert (bb["bb_mid"] >= bb["bb_lower"]).all()


def test_macd_columns_present():
    s = _series(100 + np.arange(60) * 0.5)
    out = trend.macd(s)
    assert set(["macd", "macd_signal", "macd_hist"]).issubset(out.columns)
