"""Market regime classifier — maps features to one of 10 regimes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from config.constants import MarketRegime
from features.trend import adx, ema
from features.volatility import atr, historical_volatility


@dataclass
class RegimeResult:
    regime: MarketRegime
    confidence: float
    detail: dict


class RegimeClassifier:
    """Rule-based classifier. Deterministic and fully auditable."""

    def __init__(self, adx_trend: float = 25.0, vol_high_pct: float = 0.75,
                 vol_low_pct: float = 0.25) -> None:
        self.adx_trend = adx_trend
        self.vol_high_pct = vol_high_pct
        self.vol_low_pct = vol_low_pct

    def classify(self, df: pd.DataFrame) -> RegimeResult:
        if df is None or len(df) < 50:
            return RegimeResult(MarketRegime.CHOPPY, 0.0, {"reason": "insufficient_data"})

        close = df["close"]
        adx_df = adx(df)
        adx_val = float(adx_df["adx"].dropna().iloc[-1]) if not adx_df["adx"].dropna().empty else 0.0
        plus_di = float(adx_df["plus_di"].dropna().iloc[-1]) if not adx_df["plus_di"].dropna().empty else 0.0
        minus_di = float(adx_df["minus_di"].dropna().iloc[-1]) if not adx_df["minus_di"].dropna().empty else 0.0

        ema_fast = ema(close, 20).iloc[-1]
        ema_slow = ema(close, 50).iloc[-1]
        uptrend = ema_fast > ema_slow

        hv = historical_volatility(close, 20, annualize=False)
        hv_series = hv.dropna()
        vol_pct = float(hv_series.rank(pct=True).iloc[-1]) if len(hv_series) > 10 else 0.5

        rng = close.tail(20)
        range_ratio = (rng.max() - rng.min()) / (rng.mean() or np.nan)

        detail = {"adx": adx_val, "vol_pct": vol_pct, "uptrend": uptrend,
                  "range_ratio": float(range_ratio) if np.isfinite(range_ratio) else None}

        # Priority: volatility extremes -> trend strength -> range/chop.
        if vol_pct >= self.vol_high_pct and adx_val < self.adx_trend:
            return RegimeResult(MarketRegime.HIGH_VOLATILITY, 0.7, detail)
        if vol_pct <= self.vol_low_pct and adx_val < self.adx_trend:
            return RegimeResult(MarketRegime.LOW_VOLATILITY, 0.7, detail)

        if adx_val >= self.adx_trend:
            strong = adx_val >= self.adx_trend + 10
            if plus_di >= minus_di:
                reg = MarketRegime.STRONG_UPTREND if strong else MarketRegime.WEAK_UPTREND
            else:
                reg = MarketRegime.STRONG_DOWNTREND if strong else MarketRegime.WEAK_DOWNTREND
            return RegimeResult(reg, min(1.0, adx_val / 50.0), detail)

        if np.isfinite(range_ratio) and range_ratio < 0.05:
            return RegimeResult(MarketRegime.RANGE_BOUND, 0.6, detail)

        return RegimeResult(MarketRegime.CHOPPY, 0.5, detail)
