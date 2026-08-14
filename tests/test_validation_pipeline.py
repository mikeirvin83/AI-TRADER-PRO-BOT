"""Tests for the strategy validation pipeline (Phase 4)."""
import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone

from validation.pipeline import (
    ValidationPipeline,
    PromotionGates,
    PromotionStage,
    StrategyValidationState,
)
from strategies.base_strategy import BaseStrategy, StrategySignal
from config.constants import MarketRegime, SignalDirection, StrategyStatus


# --- Fixtures ---

def _make_trending_data(n: int = 500, seed: int = 42) -> pd.DataFrame:
    """Generate synthetic uptrending OHLCV data that produces trades."""
    rng = np.random.RandomState(seed)
    base = 100.0
    prices = [base]
    for _ in range(n - 1):
        ret = rng.normal(0.0005, 0.01)  # slight upward drift
        prices.append(prices[-1] * (1 + ret))
    arr = np.array(prices)
    df = pd.DataFrame({
        'open': arr * (1 - rng.uniform(0, 0.005, n)),
        'high': arr * (1 + rng.uniform(0, 0.01, n)),
        'low': arr * (1 - rng.uniform(0, 0.01, n)),
        'close': arr,
        'volume': rng.randint(100_000, 1_000_000, n).astype(float),
    })
    df.index = pd.date_range('2024-01-01', periods=n, freq='D')
    return df


class SimpleTrendStrategy(BaseStrategy):
    """A minimal trend strategy for testing the pipeline."""
    name = "test_trend"
    version = "1.0.0"
    status = StrategyStatus.UNDER_RESEARCH
    category = "trend"
    allowed_regimes = list(MarketRegime)

    def generate_signal(self, data, features, regime=None, news=None):
        if len(data) < 30 or features.empty:
            return None
        close = float(data['close'].iloc[-1])
        ema_fast = self._last(features, 'ema_9')
        ema_slow = self._last(features, 'ema_21')
        atr = self._last(features, 'atr_14') or (close * 0.01)
        if ema_fast is None or ema_slow is None:
            return None
        if ema_fast > ema_slow:
            try:
                return StrategySignal(
                    asset=str(data.attrs.get('symbol', 'TEST')),
                    direction=SignalDirection.LONG,
                    entry=close,
                    stop=close - 2 * atr,
                    target=close + 3 * atr,
                    invalidation_condition='EMA cross reverses',
                    expiration_time=datetime.now(timezone.utc) + timedelta(hours=24),
                    strategy_name=self.name,
                    score=80,
                )
            except Exception:
                return None
        return None


# --- Tests ---

class TestValidationPipeline:
    def test_create_state(self):
        pipeline = ValidationPipeline()
        strategy = SimpleTrendStrategy()
        state = pipeline.create(strategy)
        assert state.strategy_name == "test_trend"
        assert state.current_stage == PromotionStage.RESEARCH
        assert len(state.gate_results) == 0

    def test_stage_ordering(self):
        from validation.pipeline import STAGE_ORDER
        assert STAGE_ORDER[0] == PromotionStage.RESEARCH
        assert STAGE_ORDER[-1] == PromotionStage.LIVE
        assert len(STAGE_ORDER) == 11

    def test_backtest_gate_with_data(self):
        data = _make_trending_data(500)
        pipeline = ValidationPipeline(PromotionGates(
            min_trades=1,
            min_sharpe=-10,
            max_drawdown=0.99,
            min_profit_factor=0.01,
            min_win_rate=0.01,
        ))
        strategy = SimpleTrendStrategy()
        state = pipeline.create(strategy)
        state = pipeline.run_backtest_gate(state, strategy, data, "TEST")
        assert state.backtest_result is not None
        # Should have a gate result
        assert len(state.gate_results) >= 1
        gate = state.gate_results[-1]
        assert gate.stage == PromotionStage.BACKTEST

    def test_backtest_gate_fails_on_strict_thresholds(self):
        data = _make_trending_data(200, seed=99)
        pipeline = ValidationPipeline(PromotionGates(
            min_trades=9999,  # impossibly high
            min_sharpe=5.0,
        ))
        strategy = SimpleTrendStrategy()
        state = pipeline.create(strategy)
        state = pipeline.run_backtest_gate(state, strategy, data, "TEST")
        gate = state.gate_results[-1]
        assert gate.stage == PromotionStage.BACKTEST
        assert not gate.passed  # fails because min_trades is impossibly high

    def test_wrong_stage_blocked(self):
        pipeline = ValidationPipeline()
        state = StrategyValidationState("test", current_stage=PromotionStage.PAPER)
        data = _make_trending_data(100)
        strategy = SimpleTrendStrategy()
        # OOS gate should be blocked since we're at PAPER stage
        state = pipeline.run_oos_gate(state, strategy, data)
        assert len(state.gate_results) == 0  # no gate was added

    def test_monte_carlo_gate(self):
        pipeline = ValidationPipeline(PromotionGates(
            max_mc_ruin_probability=0.50,
            max_mc_p95_drawdown=0.99,
        ))
        state = StrategyValidationState("mc_test", current_stage=PromotionStage.MONTE_CARLO)
        # Create some mildly profitable trade PnLs
        trade_pnls = [100, -50, 200, -30, 150, -80, 120, 90, -40, 60] * 5
        state = pipeline.run_monte_carlo_gate(state, trade_pnls)
        assert len(state.gate_results) == 1
        gate = state.gate_results[0]
        assert gate.stage == PromotionStage.MONTE_CARLO
        assert state.monte_carlo_result is not None

    def test_paper_gate_needs_minimum_trades(self):
        pipeline = ValidationPipeline(PromotionGates(min_paper_trades=50))
        state = StrategyValidationState("paper_test", current_stage=PromotionStage.PAPER)
        metrics = {"num_trades": 10, "duration_days": 30, "sharpe": 1.0, "max_drawdown": 0.05}
        state = pipeline.run_paper_gate(state, metrics)
        assert not state.gate_results[-1].passed  # not enough trades

    def test_stage_to_status_mapping(self):
        assert ValidationPipeline.stage_to_strategy_status(
            PromotionStage.RESEARCH) == StrategyStatus.UNDER_RESEARCH
        assert ValidationPipeline.stage_to_strategy_status(
            PromotionStage.PAPER) == StrategyStatus.WATCH
        assert ValidationPipeline.stage_to_strategy_status(
            PromotionStage.LIVE) == StrategyStatus.ACTIVE

    def test_summary(self):
        pipeline = ValidationPipeline()
        state = StrategyValidationState("test", current_stage=PromotionStage.BACKTEST)
        summary = pipeline.summary(state)
        assert summary["strategy"] == "test"
        assert summary["current_stage"] == "BACKTEST"


class TestStrategyDegradation:
    def test_healthy_strategy(self):
        from validation.strategy_degradation import StrategyDegradationMonitor, DegradationThresholds
        # Use thresholds relative to the test data scale
        monitor = StrategyDegradationMonitor(
            DegradationThresholds(retired_drawdown_pct=0.99, suspended_drawdown_pct=0.95,
                                  degraded_drawdown_pct=0.90))
        # Consistently profitable trades
        pnls = [100, 50, 200, 150, 30, 80, 120] * 10
        report = monitor.evaluate("test", StrategyStatus.ACTIVE, pnls)
        assert report.recommended_status in (StrategyStatus.ACTIVE, StrategyStatus.WATCH)

    def test_negative_expectancy_triggers_degraded(self):
        from validation.strategy_degradation import StrategyDegradationMonitor
        monitor = StrategyDegradationMonitor()
        pnls = [-100, -50, -200, 30, -150, -80, -120] * 10
        report = monitor.evaluate("bad_strat", StrategyStatus.ACTIVE, pnls)
        assert report.recommended_status in (
            StrategyStatus.DEGRADED, StrategyStatus.SUSPENDED, StrategyStatus.RETIRED)

    def test_consecutive_losses_triggers_suspension(self):
        from validation.strategy_degradation import StrategyDegradationMonitor, DegradationThresholds
        monitor = StrategyDegradationMonitor(
            DegradationThresholds(suspended_consecutive_losses=5))
        pnls = [100, 200] + [-50] * 10  # 10 consecutive losses at end
        report = monitor.evaluate("losing", StrategyStatus.ACTIVE, pnls)
        assert report.recommended_status in (
            StrategyStatus.SUSPENDED, StrategyStatus.DEGRADED, StrategyStatus.RETIRED)

    def test_empty_trades(self):
        from validation.strategy_degradation import StrategyDegradationMonitor
        monitor = StrategyDegradationMonitor()
        report = monitor.evaluate("empty", StrategyStatus.ACTIVE, [])
        assert report.recommended_status == StrategyStatus.ACTIVE


class TestBenchmarking:
    def test_compare_against_risk_free(self):
        from validation.benchmarking import StrategyBenchmarker
        benchmarker = StrategyBenchmarker(risk_free_rate=0.04)
        strategy_returns = [0.001] * 252  # ~28% annualized
        results = benchmarker.compare(strategy_returns)
        assert len(results) >= 1  # at least risk-free
        rf = next(r for r in results if r.benchmark_name == "risk_free")
        assert rf.excess_return > 0

    def test_compare_with_benchmark(self):
        from validation.benchmarking import StrategyBenchmarker
        benchmarker = StrategyBenchmarker()
        rng = np.random.RandomState(42)
        n = 252
        strategy_returns = list(rng.normal(0.001, 0.01, n))
        prices = pd.Series(np.cumprod(1 + rng.normal(0.0005, 0.01, n + 21)) * 100)
        results = benchmarker.compare(strategy_returns, prices, "SPY")
        assert len(results) >= 2  # buy_hold + risk_free at minimum


class TestEnsembleAllocator:
    def test_basic_allocation(self):
        from validation.ensemble_allocator import EnsembleAllocator
        allocator = EnsembleAllocator()
        strategies = [
            {"name": "trend_a", "category": "trend", "status": "ACTIVE",
             "sharpe": 1.5, "max_drawdown": 0.1, "profit_factor": 2.0,
             "win_rate": 0.6, "correlation_score": 0.1},
            {"name": "mom_a", "category": "momentum", "status": "ACTIVE",
             "sharpe": 1.0, "max_drawdown": 0.15, "profit_factor": 1.5,
             "win_rate": 0.55, "correlation_score": 0.2},
        ]
        result = allocator.allocate(strategies)
        assert result.total_weight > 0
        assert result.unallocated > 0  # cash reserve
        assert sum(a.weight for a in result.allocations) <= 1.0

    def test_no_eligible_strategies(self):
        from validation.ensemble_allocator import EnsembleAllocator
        allocator = EnsembleAllocator()
        result = allocator.allocate([
            {"name": "bad", "category": "trend", "status": "RETIRED",
             "sharpe": -1, "max_drawdown": 0.5, "profit_factor": 0.5,
             "win_rate": 0.3, "correlation_score": 0},
        ])
        assert result.total_weight == 0
        assert result.unallocated == 1.0


class TestTradeQualityFilter:
    def test_all_checks_pass(self):
        from validation.trade_quality_filter import TradeQualityFilter
        from config.settings import TradingMode
        from core.system_state import get_system_state
        # Must be in a trading-capable mode for no_emergency check
        st = get_system_state()
        st.transition_to(TradingMode.PAPER, "test", actor="pytest")
        f = TradeQualityFilter()
        ctx = {
            "data_quality": "CLEAN",
            "avg_volume": 500_000,
            "spread_pct": 0.001,
            "strategy_status": "ACTIVE",
            "strategy_validated": True,
            "regime_allowed": True,
            "signal_score": 85,
            "risk_reward": 2.0,
            "risk_approved": True,
        }
        decision = f.evaluate(ctx)
        assert decision.allowed
        assert len(decision.failed_checks) == 0

    def test_corrupted_data_blocks_trade(self):
        from validation.trade_quality_filter import TradeQualityFilter
        f = TradeQualityFilter()
        ctx = {
            "data_quality": "CORRUPTED",
            "avg_volume": 500_000,
            "spread_pct": 0.001,
            "strategy_status": "ACTIVE",
            "strategy_validated": True,
            "regime_allowed": True,
            "signal_score": 90,
            "risk_reward": 3.0,
            "risk_approved": True,
        }
        decision = f.evaluate(ctx)
        assert not decision.allowed
        failed_names = [c.name for c in decision.failed_checks]
        assert "market_data_valid" in failed_names

    def test_low_score_blocks_trade(self):
        from validation.trade_quality_filter import TradeQualityFilter
        f = TradeQualityFilter()
        ctx = {
            "data_quality": "CLEAN",
            "avg_volume": 500_000,
            "spread_pct": 0.001,
            "strategy_status": "ACTIVE",
            "strategy_validated": True,
            "regime_allowed": True,
            "signal_score": 50,  # below threshold
            "risk_reward": 2.0,
            "risk_approved": True,
        }
        decision = f.evaluate(ctx)
        assert not decision.allowed


class TestPortfolioRiskIntegrator:
    def test_drawdown_tracking(self):
        from risk.portfolio_risk_integrator import PortfolioRiskIntegrator
        integrator = PortfolioRiskIntegrator(initial_equity=100_000)
        integrator.update(equity=105_000)  # new peak
        integrator.update(equity=95_000)   # drawdown
        dd = integrator.get_drawdown()
        assert dd > 0.09  # ~9.5% from peak
        assert dd < 0.11

    def test_circuit_breaker_trip(self):
        from risk.portfolio_risk_integrator import PortfolioRiskIntegrator
        from config.settings import Settings
        settings = Settings(MAX_DAILY_LOSS_PCT=0.03)
        from risk.risk_engine import RiskEngine
        engine = RiskEngine(settings)
        integrator = PortfolioRiskIntegrator(100_000, engine)
        # Simulate a 5% daily loss (exceeds 3% limit)
        integrator.update(equity=95_000)
        tripped = integrator.check_circuit_breakers()
        assert tripped

    def test_risk_summary(self):
        from risk.portfolio_risk_integrator import PortfolioRiskIntegrator
        integrator = PortfolioRiskIntegrator(initial_equity=100_000)
        integrator.update(equity=100_000, open_positions=2)
        summary = integrator.get_risk_summary()
        assert "trading_allowed" in summary
        assert "limits" in summary
