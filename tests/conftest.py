"""Shared pytest fixtures.

These fixtures avoid any dependency on a live database or broker. The
SystemState singleton is reset before each test so mode-transition tests are
deterministic regardless of ordering.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from config.settings import TradingMode
from core.system_state import get_system_state


@pytest.fixture(autouse=True)
def reset_system_state():
    """Reset the global SystemState to a known baseline before each test."""
    st = get_system_state()
    # Force back to DISABLED, clearing any emergency stop from a prior test.
    if st.is_emergency_stopped():
        st.reset_emergency_stop("test-reset", actor="pytest")
    # Walk back to DISABLED through a legal path if needed.
    try:
        st.transition_to(TradingMode.DISABLED, "test-reset", actor="pytest")
    except Exception:
        pass
    yield
    if st.is_emergency_stopped():
        st.reset_emergency_stop("test-teardown", actor="pytest")


def _make_ohlcv(prices, volume=1_000_000):
    idx = pd.date_range("2024-01-01", periods=len(prices), freq="D", tz="UTC")
    close = pd.Series(prices, index=idx, dtype=float)
    high = close * 1.01
    low = close * 0.99
    open_ = close.shift(1).fillna(close.iloc[0])
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close,
         "volume": float(volume)},
        index=idx,
    )


@pytest.fixture
def clean_ohlcv():
    """A clean, trending OHLCV frame."""
    prices = list(np.linspace(100, 140, 120))
    return _make_ohlcv(prices)


@pytest.fixture
def make_ohlcv():
    return _make_ohlcv
