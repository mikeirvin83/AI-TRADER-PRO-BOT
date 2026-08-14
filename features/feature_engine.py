"""FeatureEngine — master feature builder.

Runs every indicator group over an OHLCV DataFrame and returns a single, unified
feature DataFrame. Validates that outputs are finite; logs (and drops to NaN)
any feature that produced inf/-inf. Never silently fabricates values.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import numpy as np
import pandas as pd

from config.logging_config import get_logger
from features import momentum, price_structure, trend, volatility, volume as volume_ind
from features import fair_value

log = get_logger(__name__)

REQUIRED_COLUMNS = ("open", "high", "low", "close", "volume")
MIN_BARS = 50  # enough to warm up the slowest default indicator windows


@dataclass
class FeatureResult:
    features: pd.DataFrame
    issues: List[str] = field(default_factory=list)
    ok: bool = True


class FeatureEngine:
    """Builds the full feature matrix from OHLCV data."""

    def __init__(self, min_bars: int = MIN_BARS) -> None:
        self.min_bars = min_bars

    def _validate_input(self, df: pd.DataFrame) -> None:
        missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(f"OHLCV frame missing columns: {missing}")

    def build(self, df: pd.DataFrame) -> FeatureResult:
        self._validate_input(df)
        issues: List[str] = []

        if len(df) < self.min_bars:
            issues.append(f"insufficient_bars: have {len(df)}, need {self.min_bars}")

        out = pd.DataFrame(index=df.index)

        # --- trend ---
        out["sma_20"] = trend.sma(df["close"], 20)
        out["sma_50"] = trend.sma(df["close"], 50)
        out["ema_9"] = trend.ema(df["close"], 9)
        out["ema_21"] = trend.ema(df["close"], 21)
        out["wma_20"] = trend.wma(df["close"], 20)
        out["vwap"] = trend.vwap(df)
        out = out.join(trend.macd(df["close"]))
        out = out.join(trend.adx(df))

        # --- momentum ---
        out["rsi_14"] = momentum.rsi(df["close"], 14)
        out = out.join(momentum.stochastic(df))
        out["williams_r"] = momentum.williams_r(df)
        out["roc_12"] = momentum.roc(df["close"], 12)
        out["cci_20"] = momentum.cci(df)

        # --- volatility ---
        out["atr_14"] = volatility.atr(df, 14)
        out["hv_20"] = volatility.historical_volatility(df["close"], 20)
        out = out.join(volatility.bollinger_bands(df["close"]))
        out = out.join(volatility.keltner_channels(df))

        # --- volume ---
        out["rel_volume"] = volume_ind.relative_volume(df["volume"])
        out["obv"] = volume_ind.obv(df)
        out["ad_line"] = volume_ind.accumulation_distribution(df)
        out["dollar_vol_accel"] = volume_ind.dollar_volume_acceleration(df)

        # --- structure ---
        out = out.join(price_structure.support_resistance(df))
        out["gap_pct"] = price_structure.gaps(df)
        out = out.join(price_structure.previous_high_low(df))
        out = out.join(fair_value.fair_value_gaps(df))
        out["bar_imbalance"] = fair_value.imbalance(df)

        # --- finiteness validation: replace inf with NaN and record columns ---
        inf_mask = out.replace([np.inf, -np.inf], np.nan).isna() & ~out.isna()
        bad_cols = [c for c in out.columns if inf_mask[c].any()]
        if bad_cols:
            issues.append(f"non_finite_features: {bad_cols}")
            log.warning("feature_engine_non_finite", columns=bad_cols)
        out = out.replace([np.inf, -np.inf], np.nan)

        result = FeatureResult(features=out, issues=issues, ok=len(issues) == 0)
        log.debug("feature_engine_built", n_features=out.shape[1], n_rows=out.shape[0], issues=issues)
        return result
