"""Trend indicators — implemented from scratch (vectorised pandas/numpy).

All functions accept an OHLCV DataFrame with columns
``open, high, low, close, volume`` and return a ``pd.Series`` (or DataFrame for
multi-output indicators) indexed like the input. NaNs are handled gracefully;
insufficient data yields NaN rather than raising.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _min_bars(series: pd.Series, n: int) -> bool:
    return series.notna().sum() >= n


def sma(close: pd.Series, period: int = 20) -> pd.Series:
    """Simple moving average."""
    return close.rolling(window=period, min_periods=period).mean()


def ema(close: pd.Series, period: int = 20) -> pd.Series:
    """Exponential moving average."""
    return close.ewm(span=period, adjust=False, min_periods=period).mean()


def wma(close: pd.Series, period: int = 20) -> pd.Series:
    """Weighted moving average (linear weights)."""
    weights = np.arange(1, period + 1)

    def _w(x: np.ndarray) -> float:
        return float(np.dot(x, weights) / weights.sum())

    return close.rolling(window=period, min_periods=period).apply(_w, raw=True)


def vwap(df: pd.DataFrame) -> pd.Series:
    """Volume-weighted average price (cumulative, session-agnostic).

    Uses the typical price (H+L+C)/3. For intraday session VWAP, reset per day
    upstream before calling.
    """
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    cum_vol = df["volume"].cumsum()
    cum_pv = (typical * df["volume"]).cumsum()
    return cum_pv / cum_vol.replace(0, np.nan)


def macd(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> pd.DataFrame:
    """MACD line, signal line and histogram."""
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = macd_line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    hist = macd_line - signal_line
    return pd.DataFrame(
        {"macd": macd_line, "macd_signal": signal_line, "macd_hist": hist}
    )


def adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Average Directional Index with +DI / -DI (Wilder's smoothing)."""
    high, low, close = df["high"], df["low"], df["close"]
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    plus_dm = pd.Series(plus_dm, index=df.index)
    minus_dm = pd.Series(minus_dm, index=df.index)

    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)

    # Wilder smoothing via EMA with alpha = 1/period
    atr = tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx_line = dx.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    return pd.DataFrame({"adx": adx_line, "plus_di": plus_di, "minus_di": minus_di})
