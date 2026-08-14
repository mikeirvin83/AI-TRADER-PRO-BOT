"""Volume indicators — relative volume, OBV, Accumulation/Distribution,
dollar-volume acceleration.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def relative_volume(volume: pd.Series, period: int = 20) -> pd.Series:
    """Current volume divided by its rolling average."""
    avg = volume.rolling(period, min_periods=period).mean()
    return volume / avg.replace(0, np.nan)


def obv(df: pd.DataFrame) -> pd.Series:
    """On-Balance Volume."""
    direction = np.sign(df["close"].diff()).fillna(0.0)
    return (direction * df["volume"]).cumsum()


def accumulation_distribution(df: pd.DataFrame) -> pd.Series:
    """Accumulation/Distribution line."""
    hl_range = (df["high"] - df["low"]).replace(0, np.nan)
    mfm = ((df["close"] - df["low"]) - (df["high"] - df["close"])) / hl_range
    mfv = mfm.fillna(0.0) * df["volume"]
    return mfv.cumsum()


def dollar_volume(df: pd.DataFrame) -> pd.Series:
    """Approximate traded dollar volume (typical price * volume)."""
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    return typical * df["volume"]


def dollar_volume_acceleration(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Rate of change of the dollar-volume moving average (acceleration)."""
    dv = dollar_volume(df)
    dv_ma = dv.rolling(period, min_periods=period).mean()
    return dv_ma.pct_change()
