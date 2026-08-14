"""Order manager tests — mode gating, paper fills, duplicate protection."""
from __future__ import annotations

import pytest

from config.settings import TradingMode
from core.system_state import get_system_state
from execution.order_manager import DuplicateOrderError, OrderManager


def _signal():
    return {"symbol": "SPY", "direction": "LONG", "qty": 10,
            "entry": 100.0, "strategy_name": "test"}


def test_order_rejected_when_disabled():
    om = OrderManager()
    # Default DISABLED => trading not allowed.
    with pytest.raises(RuntimeError):
        om.place_order(_signal(), next_open_price=101.0)


def test_paper_order_fills():
    get_system_state().transition_to(TradingMode.PAPER, "test", actor="pytest")
    om = OrderManager()
    ticket = om.place_order(_signal(), next_open_price=101.0)
    assert ticket.status == "FILLED"
    assert ticket.mode == TradingMode.PAPER.value
    assert ticket.symbol == "SPY"


def test_duplicate_order_blocked_in_shadow():
    # In SHADOW the order stays open (SUBMITTED), so a duplicate should raise.
    st = get_system_state()
    st.transition_to(TradingMode.PAPER, "t", actor="pytest")
    st.transition_to(TradingMode.SHADOW, "t", actor="pytest")
    om = OrderManager()
    om.place_order(_signal())
    with pytest.raises(DuplicateOrderError):
        om.place_order(_signal())
