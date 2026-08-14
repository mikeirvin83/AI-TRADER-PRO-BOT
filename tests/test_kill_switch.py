"""SystemState mode-transition and kill-switch tests.

Enforces the promotion path PAPER -> SHADOW -> LIVE (no skipping) and verifies
the emergency stop halts trading at the state layer.
"""
from __future__ import annotations

import pytest

from config.settings import TradingMode
from core.system_state import IllegalTransitionError, get_system_state


def test_default_disabled_not_trading():
    st = get_system_state()
    assert st.get_mode() == TradingMode.DISABLED
    assert st.is_trading_allowed() is False


def test_legal_promotion_path():
    st = get_system_state()
    st.transition_to(TradingMode.PAPER, "start paper", actor="pytest")
    assert st.get_mode() == TradingMode.PAPER
    assert st.is_trading_allowed() is True
    st.transition_to(TradingMode.SHADOW, "promote", actor="pytest")
    assert st.get_mode() == TradingMode.SHADOW
    st.transition_to(TradingMode.LIVE, "promote", actor="pytest")
    assert st.get_mode() == TradingMode.LIVE


def test_cannot_skip_paper_to_live():
    st = get_system_state()
    st.transition_to(TradingMode.PAPER, "start", actor="pytest")
    with pytest.raises(IllegalTransitionError):
        st.transition_to(TradingMode.LIVE, "illegal skip", actor="pytest")


def test_cannot_jump_disabled_to_live():
    st = get_system_state()
    with pytest.raises(IllegalTransitionError):
        st.transition_to(TradingMode.LIVE, "illegal", actor="pytest")


def test_cannot_jump_disabled_to_shadow():
    st = get_system_state()
    with pytest.raises(IllegalTransitionError):
        st.transition_to(TradingMode.SHADOW, "illegal", actor="pytest")


def test_emergency_stop_and_reset():
    st = get_system_state()
    st.transition_to(TradingMode.PAPER, "start", actor="pytest")
    st.engage_emergency_stop("boom", actor="pytest")
    assert st.is_emergency_stopped() is True
    assert st.is_trading_allowed() is False
    assert st.get_mode() == TradingMode.EMERGENCY_STOP
    # Cannot transition anywhere except DISABLED while stopped.
    with pytest.raises(IllegalTransitionError):
        st.transition_to(TradingMode.PAPER, "resume", actor="pytest")
    # Reset returns to DISABLED.
    st.reset_emergency_stop("cleared", actor="pytest")
    assert st.is_emergency_stopped() is False
    assert st.get_mode() == TradingMode.DISABLED


def test_history_records_transitions():
    st = get_system_state()
    st.transition_to(TradingMode.PAPER, "start", actor="pytest")
    history = st.get_history()
    assert any(h.to_mode == TradingMode.PAPER for h in history)
