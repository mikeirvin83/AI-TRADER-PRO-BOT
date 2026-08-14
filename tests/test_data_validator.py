"""Data validator tests — corruption must be caught before trading."""
from __future__ import annotations

import numpy as np
import pandas as pd

from config.constants import DataQuality
from market_data.data_validator import DataValidator


def _frame(close):
    idx = pd.date_range("2024-01-01", periods=len(close), freq="D", tz="UTC")
    close = pd.Series(close, index=idx, dtype=float)
    return pd.DataFrame({
        "open": close, "high": close * 1.01, "low": close * 0.99,
        "close": close, "volume": 1_000_000.0,
    })


def test_clean_data_passes():
    df = _frame(np.linspace(100, 110, 60))
    report = DataValidator().validate(df)
    assert report.quality in (DataQuality.CLEAN, DataQuality.WARNING)
    assert report.is_tradable is True


def test_empty_is_corrupted():
    report = DataValidator().validate(pd.DataFrame())
    assert report.quality == DataQuality.CORRUPTED
    assert report.is_tradable is False


def test_missing_columns_corrupted():
    df = pd.DataFrame({"close": [1, 2, 3]})
    report = DataValidator().validate(df)
    assert report.quality == DataQuality.CORRUPTED


def test_negative_prices_corrupted():
    df = _frame(np.linspace(100, 110, 60))
    df.iloc[10, df.columns.get_loc("close")] = -5.0
    report = DataValidator().validate(df)
    assert report.quality == DataQuality.CORRUPTED


def test_high_lt_low_corrupted():
    df = _frame(np.linspace(100, 110, 60))
    # swap high/low on one row
    row = 20
    df.iloc[row, df.columns.get_loc("high")] = 50.0
    df.iloc[row, df.columns.get_loc("low")] = 200.0
    report = DataValidator().validate(df)
    assert report.quality == DataQuality.CORRUPTED


def test_extreme_jump_corrupted():
    df = _frame(np.linspace(100, 110, 60))
    df.iloc[30, df.columns.get_loc("open")] = 1000.0  # >50% jump
    report = DataValidator().validate(df)
    assert report.quality == DataQuality.CORRUPTED
