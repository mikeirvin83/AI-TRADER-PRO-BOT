"""Price structure — support/resistance, swings, gaps, opening range, prev H/L."""
from __future__ import annotations

import numpy as np
import pandas as pd


def swing_points(df: pd.DataFrame, window: int = 5) -> pd.DataFrame:
    """Identify swing highs/lows using a symmetric rolling window."""
    highs = df["high"]
    lows = df["low"]
    swing_high = (highs == highs.rolling(2 * window + 1, center=True, min_periods=1).max())
    swing_low = (lows == lows.rolling(2 * window + 1, center=True, min_periods=1).min())
    return pd.DataFrame({"swing_high": swing_high, "swing_low": swing_low})


def support_resistance(df: pd.DataFrame, lookback: int = 50) -> pd.DataFrame:
    """Rolling nearest support (recent low) and resistance (recent high)."""
    resistance = df["high"].rolling(lookback, min_periods=1).max()
    support = df["low"].rolling(lookback, min_periods=1).min()
    return pd.DataFrame({"support": support, "resistance": resistance})


def gaps(df: pd.DataFrame) -> pd.Series:
    """Overnight/inter-bar gap percentage vs previous close."""
    prev_close = df["close"].shift(1)
    return (df["open"] - prev_close) / prev_close.replace(0, np.nan)


def previous_high_low(df: pd.DataFrame) -> pd.DataFrame:
    """Previous bar high/low (e.g. prior day levels)."""
    return pd.DataFrame({"prev_high": df["high"].shift(1), "prev_low": df["low"].shift(1)})


def opening_range(df: pd.DataFrame, n_bars: int = 3) -> pd.DataFrame:
    """Opening range high/low over the first ``n_bars`` bars of the series.

    For intraday use, slice per-session before calling. Returns constant columns
    equal to the ORB high/low for the provided frame.
    """
    if len(df) < n_bars:
        n_bars = len(df)
    orb_high = df["high"].iloc[:n_bars].max() if n_bars else np.nan
    orb_low = df["low"].iloc[:n_bars].min() if n_bars else np.nan
    return pd.DataFrame(
        {"orb_high": orb_high, "orb_low": orb_low}, index=df.index
    )
