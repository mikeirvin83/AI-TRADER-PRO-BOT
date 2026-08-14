"""Position sizing tests, including futures contract sizing."""
from __future__ import annotations

import pytest

from risk.position_sizer import PositionSizer, SizingResult


@pytest.fixture
def sizer():
    return PositionSizer()


def test_fixed_fractional_basic(sizer):
    # 100k equity, risk 1% = $1000, per-share risk = $2 => 500 shares
    # but capped by MAX_POSITION_SIZE_PCT (20% of 100k = 20k / $100 = 200 shares)
    res = sizer.fixed_fractional(100_000, 0.01, entry=100.0, stop=98.0)
    assert isinstance(res, SizingResult)
    assert res.quantity == 200  # position cap binds
    assert res.capped is True


def test_fixed_fractional_uncapped(sizer):
    # per-share risk large enough that risk sizing < position cap
    res = sizer.fixed_fractional(100_000, 0.01, entry=100.0, stop=90.0)
    # risk$ = 1000, per-share risk = 10 => 100 shares; notional 10k < 20k cap
    assert res.quantity == 100
    assert res.capped is False
    assert res.dollar_risk == pytest.approx(1000.0)


def test_invalid_stop_returns_zero(sizer):
    res = sizer.fixed_fractional(100_000, 0.01, entry=100.0, stop=100.0)
    assert res.quantity == 0
    assert res.capped is True


def test_atr_based(sizer):
    # atr 2, mult 2 => risk per share 4; risk$ 1000 => 250 shares, capped to 200
    res = sizer.atr_based(100_000, 0.01, atr=2.0, entry=100.0, atr_mult=2.0)
    assert res.quantity == 200
    assert res.method == "atr_based"


def test_futures_contracts_mes(sizer):
    # MES: entry 5000, stop 4990 => 10 pt = 40 ticks * $1.25 = $50/contract risk
    # risk$ = 1% of 100k = 1000 => 20 contracts (before cap)
    res = sizer.futures_contracts(100_000, 0.01, entry=5000.0, stop=4990.0, symbol="MES")
    assert res.method == "futures"
    # position cap: notional per contract = 5000 * 5 = 25000; 20% of 100k = 20000
    # => max 0 contracts by cap (floor(20000/25000)=0). Verify cap engaged.
    assert res.quantity == 0
    assert res.capped is True


def test_futures_contracts_within_cap(sizer):
    # Larger account so the position cap does not bind.
    res = sizer.futures_contracts(1_000_000, 0.01, entry=5000.0, stop=4990.0, symbol="MES")
    # risk$ = 10000, risk/contract = 50 => 200 contracts; cap: 20% of 1M = 200k
    # notional/contract = 25000 => max 8 contracts => cap binds to 8
    assert res.quantity == 8
    assert res.capped is True


def test_futures_unknown_symbol(sizer):
    res = sizer.futures_contracts(100_000, 0.01, entry=5000.0, stop=4990.0, symbol="XXX")
    assert res.quantity == 0
    assert "unknown_contract" in res.reason
