"""Tests for the Phase 11 shadow trading engine and loop."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from execution.shadow_engine import (
    DivergenceReport,
    ShadowEngine,
    ShadowOrderStatus,
)
from orchestration.shadow_trading_loop import ShadowTradingLoop
from validation.pipeline import PromotionStage, StrategyValidationState, ValidationPipeline


def _utc(minute: int = 0) -> datetime:
    return datetime(2026, 3, 2, 15, 0, tzinfo=timezone.utc) + timedelta(minutes=minute)


# ---------------------------------------------------------------- #
# ShadowEngine basics
# ---------------------------------------------------------------- #
def test_record_intent_creates_pending_order():
    eng = ShadowEngine(strategy="s1")
    order = eng.record_intent("AAPL", "buy", 10, 100.0)
    assert order.status is ShadowOrderStatus.PENDING
    assert order.side == "BUY"
    assert order.is_resolved is False
    assert eng.get(order.order_id) is order
    assert len(eng.pending()) == 1


def test_engine_never_exposes_a_broker():
    eng = ShadowEngine()
    assert eng.status()["broker_connected"] is False
    # No attribute that could reach a broker.
    for attr in ("executor", "broker", "client", "alpaca"):
        assert not hasattr(eng, attr)


def test_observe_market_matches_order_and_computes_divergence():
    eng = ShadowEngine()
    o = eng.record_intent("AAPL", "BUY", 10, 100.0, created_at=_utc(0))
    eng.observe_market(o.order_id, 101.0, observed_at=_utc(1))
    assert o.status is ShadowOrderStatus.MATCHED
    assert o.price_divergence == pytest.approx(0.01)
    assert o.signed_slippage == pytest.approx(1.0)  # adverse for a BUY
    assert o.latency_seconds == pytest.approx(60.0)


def test_sell_slippage_sign_is_inverted():
    eng = ShadowEngine()
    o = eng.record_intent("AAPL", "SELL", 10, 100.0)
    eng.observe_market(o.order_id, 99.0)
    assert o.signed_slippage == pytest.approx(1.0)  # receiving less = adverse
    o2 = eng.record_intent("AAPL", "SELL", 10, 100.0)
    eng.observe_market(o2.order_id, 101.0)
    assert o2.signed_slippage == pytest.approx(-1.0)  # favourable


def test_observe_market_with_no_price_marks_unfillable():
    eng = ShadowEngine()
    o = eng.record_intent("AAPL", "BUY", 10, 100.0)
    eng.observe_market(o.order_id, None)
    assert o.status is ShadowOrderStatus.UNFILLABLE
    assert o.reject_reason == "no_liquidity"
    assert o.price_divergence is None


def test_observe_unknown_order_raises():
    eng = ShadowEngine()
    with pytest.raises(KeyError):
        eng.observe_market("nope", 100.0)


def test_second_observation_is_ignored():
    eng = ShadowEngine()
    o = eng.record_intent("AAPL", "BUY", 10, 100.0)
    eng.observe_market(o.order_id, 101.0)
    eng.observe_market(o.order_id, 150.0)
    assert o.observed_price == pytest.approx(101.0)


def test_expire_stale_marks_old_pending_orders():
    eng = ShadowEngine(observation_window_seconds=60)
    eng.record_intent("AAPL", "BUY", 1, 100.0, created_at=_utc(0))
    assert eng.expire_stale(_utc(0)) == 0
    assert eng.expire_stale(_utc(5)) == 1
    assert eng.orders[0].status is ShadowOrderStatus.EXPIRED


# ---------------------------------------------------------------- #
# Divergence reporting
# ---------------------------------------------------------------- #
def test_report_with_no_orders_fails_closed():
    rep = ShadowEngine().report()
    assert rep.total_orders == 0
    assert rep.divergence_pct == 1.0
    assert "no_matched_orders" in rep.notes


def test_report_aggregates_divergence_statistics():
    eng = ShadowEngine(strategy="s")
    for observed in (100.5, 101.0, 102.0):
        o = eng.record_intent("AAPL", "BUY", 1, 100.0)
        eng.observe_market(o.order_id, observed)
    rep = eng.report()
    assert rep.total_orders == 3
    assert rep.matched_orders == 3
    assert rep.fill_rate == pytest.approx(1.0)
    assert rep.mean_divergence_pct == pytest.approx((0.005 + 0.01 + 0.02) / 3)
    assert rep.median_divergence_pct == pytest.approx(0.01)
    assert rep.worst_divergence_pct == pytest.approx(0.02)
    assert rep.mean_adverse_slippage_bps > 0


def test_fill_rate_penalised_by_unfillable_orders():
    eng = ShadowEngine()
    a = eng.record_intent("AAPL", "BUY", 1, 100.0)
    b = eng.record_intent("MSFT", "BUY", 1, 100.0)
    eng.observe_market(a.order_id, 100.1)
    eng.observe_market(b.order_id, None)
    rep = eng.report()
    assert rep.fill_rate == pytest.approx(0.5)
    assert any("fill_rate" in n for n in rep.notes)


def test_pnl_divergence_dominates_when_worse():
    eng = ShadowEngine()
    o = eng.record_intent("AAPL", "BUY", 1, 100.0)
    eng.observe_market(o.order_id, 100.1)  # 0.1% price divergence
    eng.record_pnl(paper_pnl=100.0, shadow_pnl=60.0)  # 40% pnl divergence
    rep = eng.report()
    assert rep.pnl_divergence_pct == pytest.approx(0.40)
    assert rep.divergence_pct == pytest.approx(0.40)


def test_gate_metrics_shape_matches_shadow_gate():
    eng = ShadowEngine()
    o = eng.record_intent("AAPL", "BUY", 1, 100.0)
    eng.observe_market(o.order_id, 100.2)
    metrics = eng.gate_metrics()
    assert "divergence_pct" in metrics
    assert metrics["matched_orders"] == 1


def test_tight_shadow_metrics_pass_the_pipeline_gate():
    eng = ShadowEngine()
    for _ in range(5):
        o = eng.record_intent("AAPL", "BUY", 1, 100.0)
        eng.observe_market(o.order_id, 100.05)
    pipeline = ValidationPipeline()
    state = StrategyValidationState(
        strategy_name="s", current_stage=PromotionStage.SHADOW)
    state = pipeline.run_shadow_gate(state, eng.gate_metrics())
    assert state.gate_results[-1].passed is True
    assert state.current_stage is PromotionStage.RISK_REVIEW


def test_wide_shadow_metrics_fail_the_pipeline_gate():
    eng = ShadowEngine()
    for _ in range(5):
        o = eng.record_intent("AAPL", "BUY", 1, 100.0)
        eng.observe_market(o.order_id, 130.0)  # 30% divergence
    pipeline = ValidationPipeline()
    state = StrategyValidationState(
        strategy_name="s", current_stage=PromotionStage.SHADOW)
    state = pipeline.run_shadow_gate(state, eng.gate_metrics())
    assert state.gate_results[-1].passed is False
    assert state.current_stage is PromotionStage.SHADOW


# ---------------------------------------------------------------- #
# ShadowTradingLoop
# ---------------------------------------------------------------- #
def test_loop_records_into_both_books():
    loop = ShadowTradingLoop("s", symbols=["AAPL"], starting_cash=50_000)
    loop.record_signal("AAPL", "BUY", 10, 100.0)
    assert len(loop.shadow.orders) == 1
    assert len(loop.paper.fills) == 1
    assert loop.paper.positions["AAPL"].qty == 10


def test_loop_reconcile_respects_delay():
    loop = ShadowTradingLoop("s", reconcile_delay_seconds=60)
    loop.record_signal("AAPL", "BUY", 1, 100.0)
    loop.shadow.orders[0].created_at = _utc(0)
    assert loop.reconcile({"AAPL": 100.5}, now=_utc(0)) == 0
    assert loop.reconcile({"AAPL": 100.5}, now=_utc(2)) == 1
    assert loop.shadow.orders[0].status is ShadowOrderStatus.MATCHED


def test_loop_reconcile_accumulates_pnl_divergence():
    loop = ShadowTradingLoop("s", reconcile_delay_seconds=0)
    loop.record_signal("AAPL", "BUY", 10, 100.0)
    loop.reconcile({"AAPL": 101.0})
    rep = loop.divergence_report()
    assert rep.matched_orders == 1
    assert rep.paper_pnl == pytest.approx(-1000.0)
    assert rep.shadow_pnl == pytest.approx(-1010.0)


def test_loop_status_always_reports_live_trading_false():
    loop = ShadowTradingLoop("s")
    assert loop.status()["live_trading"] is False


def test_loop_submits_to_pipeline_without_promoting_to_live():
    loop = ShadowTradingLoop("s", reconcile_delay_seconds=0)
    for _ in range(3):
        loop.record_signal("AAPL", "BUY", 1, 100.0)
    loop.reconcile({"AAPL": 100.02})
    pipeline = ValidationPipeline()
    state = StrategyValidationState(
        strategy_name="s", current_stage=PromotionStage.SHADOW)
    state = loop.submit_to_pipeline(pipeline, state)
    # Passing SHADOW advances only to RISK_REVIEW — never straight to LIVE.
    assert state.current_stage is PromotionStage.RISK_REVIEW


def test_loop_run_refuses_when_mode_disallows_shadow(monkeypatch):
    loop = ShadowTradingLoop("s")
    monkeypatch.setattr(loop, "_mode_allows_shadow", lambda: False)
    with pytest.raises(RuntimeError, match="refuses to start"):
        asyncio.run(loop.run())


def test_loop_tick_skips_when_emergency_stopped():
    from core.system_state import get_system_state

    st = get_system_state()
    st.engage_emergency_stop("test", actor="pytest")
    loop = ShadowTradingLoop("s", signal_fn=lambda: [
        {"symbol": "AAPL", "side": "BUY", "qty": 1, "price": 100.0}])
    asyncio.run(loop._tick())
    assert len(loop.shadow.orders) == 0
