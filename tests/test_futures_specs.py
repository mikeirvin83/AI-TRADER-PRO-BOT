"""Futures contract specification and tick-math tests (MES/MNQ/MYM/M2K)."""
from __future__ import annotations

import pytest

from config.constants import FUTURES_SPECS


@pytest.mark.parametrize("symbol", ["MES", "MNQ", "MYM", "M2K"])
def test_all_micro_contracts_present(symbol):
    assert symbol in FUTURES_SPECS


def test_mes_tick_value():
    spec = FUTURES_SPECS["MES"]
    # 0.25 tick * $5/pt multiplier = $1.25 per tick
    assert spec.tick_size == 0.25
    assert spec.contract_multiplier == 5.0
    assert spec.tick_value == pytest.approx(spec.tick_size * spec.contract_multiplier)
    assert spec.tick_value == pytest.approx(1.25)


def test_mnq_tick_value():
    spec = FUTURES_SPECS["MNQ"]
    assert spec.tick_size == 0.25
    assert spec.contract_multiplier == 2.0
    assert spec.tick_value == pytest.approx(0.50)


def test_mym_tick_value():
    spec = FUTURES_SPECS["MYM"]
    assert spec.tick_size == 1.0
    assert spec.contract_multiplier == 0.50
    assert spec.tick_value == pytest.approx(0.50)


def test_m2k_tick_value():
    spec = FUTURES_SPECS["M2K"]
    assert spec.tick_size == 0.10
    assert spec.contract_multiplier == 5.0
    assert spec.tick_value == pytest.approx(0.50)


def test_point_move_pnl_mes():
    """A 10-point move on 1 MES contract = 10 * $5 = $50."""
    spec = FUTURES_SPECS["MES"]
    pnl = 10 * spec.contract_multiplier
    assert pnl == pytest.approx(50.0)
