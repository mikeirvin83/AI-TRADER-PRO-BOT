"""Volatility indicators — ATR, historical volatility, Bollinger & Keltner
bands, volatility percentile.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from config.constants import TRADING_DAYS_PER_YEAR


def true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift(1)
    return pd.concat(
        [df["high"] - df["low"], (df["high"] - prev_close).abs(), (df["low"] - prev_close).abs()],
        axis=1,
    ).max(axis=1)


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range (Wilder's smoothing)."""
    tr = true_range(df)
    return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def historical_volatility(
    close: pd.Series, period: int = 20, annualize: bool = True
) -> pd.Series:
    """Annualised historical volatility from log returns."""
    log_ret = np.log(close / close.shift(1))
    vol = log_ret.rolling(period, min_periods=period).std()
    if annualize:
        vol = vol * np.sqrt(TRADING_DAYS_PER_YEAR)
    return vol


def bollinger_bands(
    close: pd.Series, period: int = 20, num_std: float = 2.0
) -> pd.DataFrame:
    """Bollinger Bands (mid, upper, lower, bandwidth, %B)."""
    mid = close.rolling(period, min_periods=period).mean()
    std = close.rolling(period, min_periods=period).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    bandwidth = (upper - lower) / mid.replace(0, np.nan)
    percent_b = (close - lower) / (upper - lower).replace(0, np.nan)
    return pd.DataFrame(
        {"bb_mid": mid, "bb_upper": upper, "bb_lower": lower,
         "bb_bandwidth": bandwidth, "bb_percent_b": percent_b}
    )


def keltner_channels(
    df: pd.DataFrame, period: int = 20, atr_mult: float = 2.0
) -> pd.DataFrame:
    """Keltner Channels using EMA mid and ATR envelope."""
    mid = df["close"].ewm(span=period, adjust=False, min_periods=period).mean()
    rng = atr(df, period)
    upper = mid + atr_mult * rng
    lower = mid - atr_mult * rng
    return pd.DataFrame({"kc_mid": mid, "kc_upper": upper, "kc_lower": lower})


def volatility_percentile(close: pd.Series, period: int = 20, lookback: int = 252) -> pd.Series:
    """Percentile rank of current volatility within a rolling lookback window."""
    hv = historical_volatility(close, period, annualize=False)
    return hv.rolling(lookback, min_periods=period).apply(
        lambda x: pd.Series(x).rank(pct=True).iloc[-1] * 100, raw=False
    )
