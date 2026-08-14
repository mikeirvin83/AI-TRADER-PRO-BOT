"""Risk engine veto and circuit breaker tests."""
from __future__ import annotations

import pytest

from config.settings import TradingMode
from core.system_state import get_system_state
from risk.risk_engine import PortfolioState, RiskEngine


@pytest.fixture
def engine():
    return RiskEngine()


@pytest.fixture
def flat_portfolio():
    return PortfolioState(
        equity=100_000, starting_equity_day=100_000,
        starting_equity_week=100_000, peak_equity=100_000,
    )


def _enable_paper():
    st = get_system_state()
    st.transition_to(TradingMode.PAPER, "test", actor="pytest")


def _good_signal():
    # risk = |100-98| * 100 = 200 => 0.2% of equity (< 1%); notional 10k (10%)
    return {"symbol": "SPY", "direction": "LONG", "entry": 100.0,
            "stop": 98.0, "quantity": 100, "notional": 10_000}


def test_trade_blocked_when_trading_not_allowed(engine, flat_portfolio):
    # Default state is DISABLED (reset fixture) => not allowed
    decision = engine.check_trade(_good_signal(), flat_portfolio)
    assert decision.allowed is False
    assert decision.reason == "trading_not_allowed"


def test_good_trade_allowed(engine, flat_portfolio):
    _enable_paper()
    decision = engine.check_trade(_good_signal(), flat_portfolio)
    assert decision.allowed is True
    assert decision.reason == "ok"


def test_exceeds_max_risk_per_trade(engine, flat_portfolio):
    _enable_paper()
    sig = _good_signal()
    sig["stop"] = 80.0  # risk = 20 * 100 = 2000 = 2% > 1%
    decision = engine.check_trade(sig, flat_portfolio)
    assert decision.allowed is False
    assert decision.reason == "exceeds_max_risk_per_trade"


def test_exceeds_position_size(engine, flat_portfolio):
    _enable_paper()
    sig = _good_signal()
    sig["notional"] = 30_000  # 30% > 20% cap
    sig["stop"] = 99.9        # keep per-trade risk tiny
    decision = engine.check_trade(sig, flat_portfolio)
    assert decision.allowed is False
    assert decision.reason == "exceeds_max_position_size"


def test_circuit_breaker_trips_on_daily_loss(engine):
    _enable_paper()
    losing = PortfolioState(
        equity=96_000, starting_equity_day=100_000,
        starting_equity_week=100_000, peak_equity=100_000,
    )
    tripped = engine.circuit_breaker_check(losing)  # 4% daily loss > 3%
    assert tripped is True
    assert engine.is_circuit_breaker_active() is True
    # Circuit breaker also engages the emergency stop -> trading halted.
    decision = engine.check_trade(_good_signal(), losing)
    assert decision.allowed is False
    assert decision.reason in ("circuit_breaker_active", "trading_not_allowed")


def test_emergency_stop_blocks_everything(engine, flat_portfolio):
    _enable_paper()
    get_system_state().engage_emergency_stop("panic", actor="pytest")
    decision = engine.check_trade(_good_signal(), flat_portfolio)
    assert decision.allowed is False
