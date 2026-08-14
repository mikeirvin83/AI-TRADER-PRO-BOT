"""Strategy Promotion Pipeline.

Implements the full promotion lifecycle from Section 11 of the spec:
  RESEARCH → HYPOTHESIS → BACKTEST → OUT_OF_SAMPLE → WALK_FORWARD
  → MONTE_CARLO → PAPER → SHADOW → RISK_REVIEW → APPROVAL → LIVE

No strategy may advance to the next stage without passing the current gate.
No stage can be skipped. The pipeline is the single authority on whether a
strategy is allowed to trade.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from config.constants import StrategyStatus
from config.logging_config import get_logger
from config.settings import get_settings
from backtesting.backtest_engine import BacktestConfig, BacktestEngine, BacktestResult
from backtesting.metrics import PerformanceMetrics
from backtesting.monte_carlo import MonteCarloSimulator
from backtesting.walk_forward import WalkForwardTester, WalkForwardResult
from research.overfitting_detector import OverfittingDetector, OverfittingReport
from strategies.base_strategy import BaseStrategy

log = get_logger(__name__)


class PromotionStage(str, Enum):
    RESEARCH = "RESEARCH"
    HYPOTHESIS = "HYPOTHESIS"
    BACKTEST = "BACKTEST"
    OUT_OF_SAMPLE = "OUT_OF_SAMPLE"
    WALK_FORWARD = "WALK_FORWARD"
    MONTE_CARLO = "MONTE_CARLO"
    PAPER = "PAPER"
    SHADOW = "SHADOW"
    RISK_REVIEW = "RISK_REVIEW"
    APPROVAL = "APPROVAL"
    LIVE = "LIVE"


# Ordered stages — a strategy MUST pass each in sequence.
STAGE_ORDER = list(PromotionStage)


@dataclass
class GateResult:
    """Result of evaluating a single promotion gate."""
    stage: PromotionStage
    passed: bool
    reason: str = ""
    metrics: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PromotionGates:
    """Minimum thresholds a strategy must clear at each gate."""
    # Backtest gate
    min_trades: int = 30
    min_sharpe: float = 0.5
    max_drawdown: float = 0.25
    min_profit_factor: float = 1.2
    min_win_rate: float = 0.35
    min_expectancy: float = 0.0  # must be positive

    # Out-of-sample gate
    oos_min_sharpe: float = 0.3
    oos_max_drawdown: float = 0.30
    oos_min_profit_factor: float = 1.0

    # Walk-forward gate
    min_wf_efficiency: float = 0.4  # OOS/IS return ratio
    min_wf_windows_passed: int = 3  # must pass in at least 3 windows

    # Monte Carlo gate
    max_mc_ruin_probability: float = 0.05  # < 5% probability of ruin
    max_mc_p95_drawdown: float = 0.35

    # Paper trading gate
    min_paper_trades: int = 50
    min_paper_duration_days: int = 14
    min_paper_sharpe: float = 0.3
    max_paper_drawdown: float = 0.20

    # Shadow gate
    max_divergence_pct: float = 0.10  # paper vs live divergence < 10%

    # Overfitting gate
    max_param_sensitivity: float = 0.5
    max_is_oos_degradation: float = 0.5


@dataclass
class StrategyValidationState:
    """Tracks a strategy's progress through the promotion pipeline."""
    strategy_name: str
    current_stage: PromotionStage = PromotionStage.RESEARCH
    gate_results: List[GateResult] = field(default_factory=list)
    backtest_result: Optional[Dict[str, Any]] = None
    oos_result: Optional[Dict[str, Any]] = None
    walk_forward_result: Optional[Dict[str, Any]] = None
    monte_carlo_result: Optional[Dict[str, Any]] = None
    overfitting_report: Optional[Dict[str, Any]] = None
    paper_metrics: Optional[Dict[str, Any]] = None
    shadow_metrics: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def next_stage(self) -> Optional[PromotionStage]:
        idx = STAGE_ORDER.index(self.current_stage)
        return STAGE_ORDER[idx + 1] if idx + 1 < len(STAGE_ORDER) else None

    def can_advance(self) -> bool:
        if not self.gate_results:
            return False
        return self.gate_results[-1].passed and self.gate_results[-1].stage == self.current_stage


class ValidationPipeline:
    """Orchestrates the full strategy validation lifecycle.

    Usage::

        pipeline = ValidationPipeline()
        state = pipeline.create(strategy)
        state = pipeline.run_backtest_gate(state, strategy, data)
        state = pipeline.run_oos_gate(state, strategy, oos_data)
        state = pipeline.run_walk_forward_gate(state, strategy, full_data)
        state = pipeline.run_monte_carlo_gate(state, trade_pnls)
        # ... paper trading happens externally ...
        state = pipeline.run_paper_gate(state, paper_metrics)
    """

    def __init__(self, gates: Optional[PromotionGates] = None) -> None:
        self.gates = gates or PromotionGates()
        self.settings = get_settings()
        self._states: Dict[str, StrategyValidationState] = {}

    def create(self, strategy: BaseStrategy) -> StrategyValidationState:
        state = StrategyValidationState(strategy_name=strategy.name)
        self._states[strategy.name] = state
        log.info("validation_created", strategy=strategy.name)
        return state

    def get_state(self, name: str) -> Optional[StrategyValidationState]:
        return self._states.get(name)

    def _advance(self, state: StrategyValidationState) -> StrategyValidationState:
        nxt = state.next_stage()
        if nxt and state.can_advance():
            log.info("stage_advanced", strategy=state.strategy_name,
                     from_stage=state.current_stage.value, to_stage=nxt.value)
            state.current_stage = nxt
            state.last_updated = datetime.now(timezone.utc)
        return state

    # ------------------------------------------------------------------ #
    # BACKTEST GATE
    # ------------------------------------------------------------------ #
    def run_backtest_gate(
        self,
        state: StrategyValidationState,
        strategy: BaseStrategy,
        data: pd.DataFrame,
        symbol: str = "TEST",
        config: Optional[BacktestConfig] = None,
    ) -> StrategyValidationState:
        if state.current_stage not in (PromotionStage.RESEARCH, PromotionStage.HYPOTHESIS,
                                        PromotionStage.BACKTEST):
            log.warning("wrong_stage_for_backtest", stage=state.current_stage.value)
            return state

        state.current_stage = PromotionStage.BACKTEST
        engine = BacktestEngine(config or BacktestConfig())
        result = engine.run(strategy, data, symbol)
        m = result.metrics

        reasons: List[str] = []
        if m.num_trades < self.gates.min_trades:
            reasons.append(f"trades={m.num_trades}<{self.gates.min_trades}")
        if m.sharpe < self.gates.min_sharpe:
            reasons.append(f"sharpe={m.sharpe:.2f}<{self.gates.min_sharpe}")
        if m.max_drawdown > self.gates.max_drawdown:
            reasons.append(f"drawdown={m.max_drawdown:.2f}>{self.gates.max_drawdown}")
        if m.profit_factor < self.gates.min_profit_factor:
            reasons.append(f"pf={m.profit_factor:.2f}<{self.gates.min_profit_factor}")
        if m.win_rate < self.gates.min_win_rate:
            reasons.append(f"wr={m.win_rate:.2f}<{self.gates.min_win_rate}")
        if m.expectancy <= self.gates.min_expectancy:
            reasons.append(f"expectancy={m.expectancy:.2f}<=0")

        passed = len(reasons) == 0
        gate = GateResult(PromotionStage.BACKTEST, passed,
                          "; ".join(reasons) if reasons else "all_checks_passed",
                          m.to_dict())
        state.gate_results.append(gate)
        state.backtest_result = result.to_dict()
        log.info("backtest_gate", strategy=state.strategy_name, passed=passed,
                 trades=m.num_trades, sharpe=round(m.sharpe, 3))
        return self._advance(state)

    # ------------------------------------------------------------------ #
    # OUT-OF-SAMPLE GATE
    # ------------------------------------------------------------------ #
    def run_oos_gate(
        self,
        state: StrategyValidationState,
        strategy: BaseStrategy,
        oos_data: pd.DataFrame,
        symbol: str = "TEST",
        config: Optional[BacktestConfig] = None,
    ) -> StrategyValidationState:
        if state.current_stage != PromotionStage.OUT_OF_SAMPLE:
            log.warning("wrong_stage_for_oos", stage=state.current_stage.value)
            return state

        engine = BacktestEngine(config or BacktestConfig())
        result = engine.run(strategy, oos_data, symbol)
        m = result.metrics

        reasons: List[str] = []
        if m.sharpe < self.gates.oos_min_sharpe:
            reasons.append(f"oos_sharpe={m.sharpe:.2f}<{self.gates.oos_min_sharpe}")
        if m.max_drawdown > self.gates.oos_max_drawdown:
            reasons.append(f"oos_dd={m.max_drawdown:.2f}>{self.gates.oos_max_drawdown}")
        if m.profit_factor < self.gates.oos_min_profit_factor:
            reasons.append(f"oos_pf={m.profit_factor:.2f}<{self.gates.oos_min_profit_factor}")

        passed = len(reasons) == 0
        gate = GateResult(PromotionStage.OUT_OF_SAMPLE, passed,
                          "; ".join(reasons) if reasons else "oos_passed",
                          m.to_dict())
        state.gate_results.append(gate)
        state.oos_result = result.to_dict()
        log.info("oos_gate", strategy=state.strategy_name, passed=passed)
        return self._advance(state)

    # ------------------------------------------------------------------ #
    # WALK-FORWARD GATE
    # ------------------------------------------------------------------ #
    def run_walk_forward_gate(
        self,
        state: StrategyValidationState,
        strategy: BaseStrategy,
        data: pd.DataFrame,
        symbol: str = "TEST",
        n_windows: int = 5,
    ) -> StrategyValidationState:
        if state.current_stage != PromotionStage.WALK_FORWARD:
            log.warning("wrong_stage_for_wf", stage=state.current_stage.value)
            return state

        tester = WalkForwardTester(n_windows=n_windows)
        result = tester.run(strategy, data, symbol)

        windows_positive = sum(1 for w in result.windows if w.get("oos_return", 0) > 0)
        reasons: List[str] = []
        if result.efficiency < self.gates.min_wf_efficiency:
            reasons.append(f"wf_eff={result.efficiency:.2f}<{self.gates.min_wf_efficiency}")
        if windows_positive < self.gates.min_wf_windows_passed:
            reasons.append(f"positive_windows={windows_positive}<{self.gates.min_wf_windows_passed}")

        passed = len(reasons) == 0
        gate = GateResult(PromotionStage.WALK_FORWARD, passed,
                          "; ".join(reasons) if reasons else "wf_passed",
                          {"efficiency": result.efficiency,
                           "n_windows": len(result.windows),
                           "positive_windows": windows_positive})
        state.gate_results.append(gate)
        state.walk_forward_result = {"efficiency": result.efficiency,
                                      "windows": result.windows,
                                      "aggregate": result.aggregate}
        log.info("walk_forward_gate", strategy=state.strategy_name, passed=passed,
                 efficiency=round(result.efficiency, 3))
        return self._advance(state)

    # ------------------------------------------------------------------ #
    # MONTE CARLO GATE
    # ------------------------------------------------------------------ #
    def run_monte_carlo_gate(
        self,
        state: StrategyValidationState,
        trade_pnls: List[float],
        initial_capital: float = 100_000.0,
        n_simulations: int = 10_000,
    ) -> StrategyValidationState:
        if state.current_stage != PromotionStage.MONTE_CARLO:
            log.warning("wrong_stage_for_mc", stage=state.current_stage.value)
            return state

        # Convert absolute PnLs to fractional returns for the MC simulator
        if initial_capital > 0 and trade_pnls:
            fractional_returns = [p / initial_capital for p in trade_pnls]
        else:
            fractional_returns = trade_pnls

        sim = MonteCarloSimulator(n_simulations=n_simulations)
        result = sim.run(fractional_returns)

        reasons: List[str] = []
        if result.probability_of_ruin > self.gates.max_mc_ruin_probability:
            reasons.append(f"ruin_prob={result.probability_of_ruin:.3f}>{self.gates.max_mc_ruin_probability}")
        if result.p95_max_drawdown > self.gates.max_mc_p95_drawdown:
            reasons.append(f"mc_dd_p95={result.p95_max_drawdown:.3f}>{self.gates.max_mc_p95_drawdown}")

        passed = len(reasons) == 0
        gate = GateResult(PromotionStage.MONTE_CARLO, passed,
                          "; ".join(reasons) if reasons else "mc_passed",
                          result.to_dict())
        state.gate_results.append(gate)
        state.monte_carlo_result = result.to_dict()
        log.info("monte_carlo_gate", strategy=state.strategy_name, passed=passed,
                 ruin_prob=round(result.probability_of_ruin, 4))
        return self._advance(state)

    # ------------------------------------------------------------------ #
    # OVERFITTING CHECK (cross-cutting, run after backtest+OOS)
    # ------------------------------------------------------------------ #
    def run_overfitting_check(
        self,
        state: StrategyValidationState,
        is_return: float,
        oos_return: float,
        wf_efficiency: float,
        param_grid_returns: Optional[List[float]] = None,
    ) -> OverfittingReport:
        detector = OverfittingDetector(
            max_sensitivity=self.gates.max_param_sensitivity,
            max_degradation=self.gates.max_is_oos_degradation,
        )
        report = detector.evaluate(is_return, oos_return, wf_efficiency, param_grid_returns)
        state.overfitting_report = {
            "is_overfit": report.is_overfit,
            "walk_forward_efficiency": report.walk_forward_efficiency,
            "param_sensitivity": report.param_sensitivity,
            "degradation": report.degradation,
            "notes": report.notes,
        }
        log.info("overfitting_check", strategy=state.strategy_name,
                 is_overfit=report.is_overfit)
        return report

    # ------------------------------------------------------------------ #
    # PAPER TRADING GATE
    # ------------------------------------------------------------------ #
    def run_paper_gate(
        self,
        state: StrategyValidationState,
        paper_metrics: Dict[str, Any],
    ) -> StrategyValidationState:
        if state.current_stage != PromotionStage.PAPER:
            log.warning("wrong_stage_for_paper", stage=state.current_stage.value)
            return state

        n_trades = paper_metrics.get("num_trades", 0)
        duration_days = paper_metrics.get("duration_days", 0)
        sharpe = paper_metrics.get("sharpe", 0.0)
        max_dd = paper_metrics.get("max_drawdown", 1.0)

        reasons: List[str] = []
        if n_trades < self.gates.min_paper_trades:
            reasons.append(f"paper_trades={n_trades}<{self.gates.min_paper_trades}")
        if duration_days < self.gates.min_paper_duration_days:
            reasons.append(f"paper_days={duration_days}<{self.gates.min_paper_duration_days}")
        if sharpe < self.gates.min_paper_sharpe:
            reasons.append(f"paper_sharpe={sharpe:.2f}<{self.gates.min_paper_sharpe}")
        if max_dd > self.gates.max_paper_drawdown:
            reasons.append(f"paper_dd={max_dd:.2f}>{self.gates.max_paper_drawdown}")

        passed = len(reasons) == 0
        gate = GateResult(PromotionStage.PAPER, passed,
                          "; ".join(reasons) if reasons else "paper_passed",
                          paper_metrics)
        state.gate_results.append(gate)
        state.paper_metrics = paper_metrics
        log.info("paper_gate", strategy=state.strategy_name, passed=passed)
        return self._advance(state)

    # ------------------------------------------------------------------ #
    # SHADOW GATE
    # ------------------------------------------------------------------ #
    def run_shadow_gate(
        self,
        state: StrategyValidationState,
        shadow_metrics: Dict[str, Any],
    ) -> StrategyValidationState:
        if state.current_stage != PromotionStage.SHADOW:
            log.warning("wrong_stage_for_shadow", stage=state.current_stage.value)
            return state

        divergence = shadow_metrics.get("divergence_pct", 1.0)
        reasons: List[str] = []
        if divergence > self.gates.max_divergence_pct:
            reasons.append(f"divergence={divergence:.2f}>{self.gates.max_divergence_pct}")

        passed = len(reasons) == 0
        gate = GateResult(PromotionStage.SHADOW, passed,
                          "; ".join(reasons) if reasons else "shadow_passed",
                          shadow_metrics)
        state.gate_results.append(gate)
        state.shadow_metrics = shadow_metrics
        log.info("shadow_gate", strategy=state.strategy_name, passed=passed)
        return self._advance(state)

    # ------------------------------------------------------------------ #
    # FULL AUTOMATED VALIDATION (backtest → MC in one call)
    # ------------------------------------------------------------------ #
    def run_full_validation(
        self,
        strategy: BaseStrategy,
        is_data: pd.DataFrame,
        oos_data: pd.DataFrame,
        full_data: pd.DataFrame,
        symbol: str = "TEST",
    ) -> StrategyValidationState:
        """Run the deterministic validation stages (backtest → MC) in sequence.

        Paper and shadow gates cannot be run here — they require real-time
        trading data accumulated over days/weeks.
        """
        state = self.create(strategy)

        # 1. Backtest
        state = self.run_backtest_gate(state, strategy, is_data, symbol)
        if not state.can_advance() and state.current_stage == PromotionStage.BACKTEST:
            return state

        # 2. Out-of-sample
        state = self.run_oos_gate(state, strategy, oos_data, symbol)
        if not state.can_advance() and state.current_stage == PromotionStage.OUT_OF_SAMPLE:
            return state

        # 3. Walk-forward
        state = self.run_walk_forward_gate(state, strategy, full_data, symbol)
        if not state.can_advance() and state.current_stage == PromotionStage.WALK_FORWARD:
            return state

        # 4. Monte Carlo (using backtest trades)
        bt = state.backtest_result or {}
        trade_pnls = [t.get("pnl", 0) for t in bt.get("trades", []) if t.get("status") == "closed"]
        if trade_pnls:
            state = self.run_monte_carlo_gate(state, trade_pnls)

        # 5. Overfitting check
        is_ret = bt.get("metrics", {}).get("total_return", 0)
        oos_ret = (state.oos_result or {}).get("metrics", {}).get("total_return", 0)
        wf_eff = (state.walk_forward_result or {}).get("efficiency", 0)
        self.run_overfitting_check(state, is_ret, oos_ret, wf_eff)

        return state

    # ------------------------------------------------------------------ #
    # STATUS MAPPING
    # ------------------------------------------------------------------ #
    @staticmethod
    def stage_to_strategy_status(stage: PromotionStage) -> StrategyStatus:
        """Map a pipeline stage to the strategy's operational status."""
        mapping = {
            PromotionStage.RESEARCH: StrategyStatus.UNDER_RESEARCH,
            PromotionStage.HYPOTHESIS: StrategyStatus.UNDER_RESEARCH,
            PromotionStage.BACKTEST: StrategyStatus.UNDER_RESEARCH,
            PromotionStage.OUT_OF_SAMPLE: StrategyStatus.UNDER_RESEARCH,
            PromotionStage.WALK_FORWARD: StrategyStatus.UNDER_RESEARCH,
            PromotionStage.MONTE_CARLO: StrategyStatus.UNDER_RESEARCH,
            PromotionStage.PAPER: StrategyStatus.WATCH,
            PromotionStage.SHADOW: StrategyStatus.WATCH,
            PromotionStage.RISK_REVIEW: StrategyStatus.WATCH,
            PromotionStage.APPROVAL: StrategyStatus.WATCH,
            PromotionStage.LIVE: StrategyStatus.ACTIVE,
        }
        return mapping.get(stage, StrategyStatus.UNDER_RESEARCH)

    def summary(self, state: StrategyValidationState) -> Dict[str, Any]:
        return {
            "strategy": state.strategy_name,
            "current_stage": state.current_stage.value,
            "gates_passed": sum(1 for g in state.gate_results if g.passed),
            "gates_failed": sum(1 for g in state.gate_results if not g.passed),
            "is_overfit": (state.overfitting_report or {}).get("is_overfit"),
            "status": self.stage_to_strategy_status(state.current_stage).value,
            "gate_details": [{"stage": g.stage.value, "passed": g.passed,
                              "reason": g.reason} for g in state.gate_results],
        }
