"""Fair-value gaps & imbalances (data-honest, no fabricated levels).

A fair-value gap (FVG) is a 3-bar imbalance where the wicks of bar[i-1] and
bar[i+1] do not overlap, leaving an untraded price void on bar[i]. We only
flag structures that are directly observable in the OHLC data.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def fair_value_gaps(df: pd.DataFrame) -> pd.DataFrame:
    """Detect bullish/bearish 3-bar fair-value gaps.

    Bullish FVG at bar i: low[i+1] > high[i-1]  (gap between them).
    Bearish FVG at bar i: high[i+1] < low[i-1].
    The gap is attributed to the middle bar i.
    """
    high = df["high"]
    low = df["low"]
    prev_high = high.shift(1)
    prev_low = low.shift(1)
    next_high = high.shift(-1)
    next_low = low.shift(-1)

    bullish = next_low > prev_high
    bearish = next_high < prev_low

    gap_size = pd.Series(np.nan, index=df.index)
    gap_size = gap_size.mask(bullish, next_low - prev_high)
    gap_size = gap_size.mask(bearish, prev_low - next_high)

    return pd.DataFrame(
        {"fvg_bullish": bullish.fillna(False),
         "fvg_bearish": bearish.fillna(False),
         "fvg_size": gap_size}
    )


def imbalance(df: pd.DataFrame) -> pd.Series:
    """Simple bar imbalance: signed body size relative to range (-1..1)."""
    rng = (df["high"] - df["low"]).replace(0, np.nan)
    return (df["close"] - df["open"]) / rng
