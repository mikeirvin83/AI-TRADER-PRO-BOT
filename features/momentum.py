"""Momentum indicators — RSI, Stochastic, Williams %R, ROC, CCI.

Implemented from scratch for auditability. Inputs are OHLCV DataFrames or the
relevant price Series; outputs are Series/DataFrames aligned to the input index.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index (Wilder's smoothing)."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    # When avg_loss == 0 and avg_gain > 0, RSI is 100.
    out = out.where(avg_loss != 0, other=100.0)
    return out


def stochastic(
    df: pd.DataFrame, k_period: int = 14, d_period: int = 3
) -> pd.DataFrame:
    """Stochastic oscillator %K and %D."""
    low_min = df["low"].rolling(k_period, min_periods=k_period).min()
    high_max = df["high"].rolling(k_period, min_periods=k_period).max()
    percent_k = 100 * (df["close"] - low_min) / (high_max - low_min).replace(0, np.nan)
    percent_d = percent_k.rolling(d_period, min_periods=d_period).mean()
    return pd.DataFrame({"stoch_k": percent_k, "stoch_d": percent_d})


def williams_r(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Williams %R (range -100..0)."""
    high_max = df["high"].rolling(period, min_periods=period).max()
    low_min = df["low"].rolling(period, min_periods=period).min()
    return -100 * (high_max - df["close"]) / (high_max - low_min).replace(0, np.nan)


def roc(close: pd.Series, period: int = 12) -> pd.Series:
    """Rate of change (percent)."""
    return 100 * (close - close.shift(period)) / close.shift(period)


def cci(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Commodity Channel Index."""
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    sma_tp = tp.rolling(period, min_periods=period).mean()
    mean_dev = (tp - sma_tp).abs().rolling(period, min_periods=period).mean()
    return (tp - sma_tp) / (0.015 * mean_dev.replace(0, np.nan))
