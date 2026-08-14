"""Data validator — detects corruption before data is ever used for trading.

Returns a :class:`ValidationReport` with a :class:`DataQuality` verdict. If the
verdict is ``CORRUPTED`` the caller MUST NOT trade on the data.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import numpy as np
import pandas as pd

from config.constants import DataQuality, Timeframe
from config.logging_config import get_logger

log = get_logger(__name__)


@dataclass
class ValidationReport:
    quality: DataQuality
    reasons: List[str] = field(default_factory=list)
    n_rows: int = 0

    @property
    def is_tradable(self) -> bool:
        return self.quality != DataQuality.CORRUPTED


class DataValidator:
    """Validates OHLCV integrity."""

    def __init__(
        self,
        sigma_threshold: float = 3.0,
        max_gap_pct: float = 0.50,
        rolling_window: int = 20,
    ) -> None:
        self.sigma_threshold = sigma_threshold
        self.max_gap_pct = max_gap_pct
        self.rolling_window = rolling_window

    def validate(self, df: pd.DataFrame, timeframe: Timeframe | None = None) -> ValidationReport:
        reasons: List[str] = []
        warnings: List[str] = []

        if df is None or df.empty:
            return ValidationReport(DataQuality.CORRUPTED, ["empty_dataframe"], 0)

        required = {"open", "high", "low", "close", "volume"}
        missing = required - set(df.columns)
        if missing:
            return ValidationReport(DataQuality.CORRUPTED, [f"missing_columns:{sorted(missing)}"], len(df))

        # --- zero / negative / null prices => corruption ---
        price_cols = ["open", "high", "low", "close"]
        if df[price_cols].isna().any().any():
            reasons.append("null_prices")
        if (df[price_cols] <= 0).any().any():
            reasons.append("non_positive_prices")

        # --- OHLC internal consistency ---
        bad_hl = (df["high"] < df["low"]).sum()
        if bad_hl:
            reasons.append(f"high_lt_low:{int(bad_hl)}")
        bad_range = (
            (df["high"] < df[["open", "close"]].max(axis=1))
            | (df["low"] > df[["open", "close"]].min(axis=1))
        ).sum()
        if bad_range:
            reasons.append(f"ohlc_out_of_range:{int(bad_range)}")

        # --- duplicate timestamps ---
        dup = int(df.index.duplicated().sum())
        if dup:
            reasons.append(f"duplicate_timestamps:{dup}")

        # --- out-of-order timestamps ---
        if not df.index.is_monotonic_increasing:
            reasons.append("out_of_order_timestamps")

        # --- gaps in the time series (warning unless timeframe known & large) ---
        if timeframe is not None and len(df.index) > 2 and isinstance(df.index, pd.DatetimeIndex):
            deltas = df.index.to_series().diff().dropna().dt.total_seconds()
            expected = timeframe.seconds
            big_gaps = int((deltas > expected * 5).sum())
            if big_gaps:
                warnings.append(f"time_gaps:{big_gaps}")

        # --- extreme bar-to-bar jumps (> max_gap_pct) => corruption ---
        prev_close = df["close"].shift(1)
        jump = ((df["open"] - prev_close).abs() / prev_close.replace(0, np.nan)).dropna()
        extreme = int((jump > self.max_gap_pct).sum())
        if extreme:
            reasons.append(f"extreme_price_jump:{extreme}")

        # --- bad ticks: > N sigma from rolling mean (warning) ---
        roll_mean = df["close"].rolling(self.rolling_window, min_periods=self.rolling_window).mean()
        roll_std = df["close"].rolling(self.rolling_window, min_periods=self.rolling_window).std()
        z = (df["close"] - roll_mean).abs() / roll_std.replace(0, np.nan)
        outliers = int((z > self.sigma_threshold).sum())
        if outliers:
            warnings.append(f"price_outliers:{outliers}")

        # --- volume anomalies ---
        if (df["volume"] < 0).any():
            reasons.append("negative_volume")
        vol_mean = df["volume"].rolling(self.rolling_window, min_periods=self.rolling_window).mean()
        vol_spike = int((df["volume"] > vol_mean * 20).sum())
        if vol_spike:
            warnings.append(f"volume_spikes:{vol_spike}")

        if reasons:
            quality = DataQuality.CORRUPTED
        elif warnings:
            quality = DataQuality.WARNING
        else:
            quality = DataQuality.CLEAN

        report = ValidationReport(quality, reasons + warnings, len(df))
        if quality == DataQuality.CORRUPTED:
            log.error("data_corrupted", reasons=reasons, rows=len(df))
        elif quality == DataQuality.WARNING:
            log.warning("data_warning", warnings=warnings, rows=len(df))
        return report
