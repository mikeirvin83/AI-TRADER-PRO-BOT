"""Strategy Degradation Monitor.

Continuously evaluates active strategies for signs of deterioration.
Flags strategies as DEGRADED or SUSPENDED when performance drops below
acceptable thresholds, per Section 45 of the spec.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np

from config.constants import StrategyStatus
from config.logging_config import get_logger

log = get_logger(__name__)


@dataclass
class DegradationThresholds:
    """Thresholds that trigger degradation / suspension / retirement."""
    # Rolling window sizes (in trades)
    rolling_window: int = 50

    # WATCH triggers
    watch_expectancy_drop_pct: float = 0.30    # 30% drop in expectancy
    watch_win_rate_drop_pct: float = 0.20      # 20% drop in win rate

    # DEGRADED triggers
    degraded_expectancy: float = 0.0           # expectancy goes negative
    degraded_drawdown_pct: float = 0.15        # strategy-level drawdown > 15%
    degraded_sharpe: float = 0.0               # Sharpe goes negative

    # SUSPENDED triggers
    suspended_consecutive_losses: int = 10     # 10 consecutive losers
    suspended_drawdown_pct: float = 0.25       # > 25% drawdown

    # RETIRED triggers
    retired_drawdown_pct: float = 0.40         # > 40% strategy drawdown
    retired_negative_expectancy_trades: int = 100  # 100+ trades with negative expectancy

    # Live vs backtest divergence
    max_live_backtest_divergence: float = 0.50  # > 50% worse than backtest


@dataclass
class DegradationReport:
    strategy_name: str
    current_status: StrategyStatus
    recommended_status: StrategyStatus
    reasons: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def should_change(self) -> bool:
        return self.recommended_status != self.current_status


class StrategyDegradationMonitor:
    """Monitors active strategies for performance degradation."""

    def __init__(self, thresholds: Optional[DegradationThresholds] = None) -> None:
        self.thresholds = thresholds or DegradationThresholds()

    def evaluate(
        self,
        strategy_name: str,
        current_status: StrategyStatus,
        trade_pnls: List[float],
        backtest_expectancy: Optional[float] = None,
        backtest_win_rate: Optional[float] = None,
        backtest_sharpe: Optional[float] = None,
    ) -> DegradationReport:
        """Evaluate a strategy's recent trade history for degradation."""
        t = self.thresholds
        reasons: List[str] = []
        recommended = current_status
        metrics: Dict[str, Any] = {}

        if not trade_pnls:
            return DegradationReport(strategy_name, current_status, current_status,
                                     ["no_trades"], metrics)

        arr = np.array(trade_pnls, dtype=float)
        n = len(arr)

        # Rolling metrics
        window = arr[-t.rolling_window:] if n >= t.rolling_window else arr
        expectancy = float(np.mean(window))
        wins = window[window > 0]
        losses = window[window < 0]
        win_rate = float(len(wins) / len(window)) if len(window) > 0 else 0
        sharpe_approx = float(np.mean(window) / np.std(window)) if np.std(window) > 0 else 0

        # Equity curve and drawdown for this strategy
        cumulative = np.cumsum(arr)
        running_max = np.maximum.accumulate(cumulative)
        # Avoid division by zero for drawdown
        with np.errstate(divide='ignore', invalid='ignore'):
            dd_arr = np.where(running_max > 0, (running_max - cumulative) / running_max, 0)
        max_dd = float(np.max(dd_arr)) if len(dd_arr) > 0 else 0

        # Consecutive losses
        consec_losses = 0
        for pnl in reversed(arr):
            if pnl < 0:
                consec_losses += 1
            else:
                break

        metrics = {
            "rolling_expectancy": round(expectancy, 4),
            "rolling_win_rate": round(win_rate, 4),
            "rolling_sharpe": round(sharpe_approx, 4),
            "strategy_max_drawdown": round(max_dd, 4),
            "consecutive_losses": consec_losses,
            "total_trades": n,
        }

        # --- RETIRED checks (most severe) ---
        if max_dd > t.retired_drawdown_pct:
            reasons.append(f"drawdown {max_dd:.1%} > {t.retired_drawdown_pct:.0%} → RETIRED")
            recommended = StrategyStatus.RETIRED
        elif n >= t.retired_negative_expectancy_trades and expectancy < 0:
            reasons.append(f"negative expectancy over {n} trades → RETIRED")
            recommended = StrategyStatus.RETIRED

        # --- SUSPENDED checks ---
        elif consec_losses >= t.suspended_consecutive_losses:
            reasons.append(f"{consec_losses} consecutive losses → SUSPENDED")
            recommended = StrategyStatus.SUSPENDED
        elif max_dd > t.suspended_drawdown_pct:
            reasons.append(f"drawdown {max_dd:.1%} > {t.suspended_drawdown_pct:.0%} → SUSPENDED")
            recommended = StrategyStatus.SUSPENDED

        # --- DEGRADED checks ---
        elif expectancy <= t.degraded_expectancy:
            reasons.append(f"negative expectancy ({expectancy:.4f}) → DEGRADED")
            recommended = StrategyStatus.DEGRADED
        elif max_dd > t.degraded_drawdown_pct:
            reasons.append(f"drawdown {max_dd:.1%} > {t.degraded_drawdown_pct:.0%} → DEGRADED")
            recommended = StrategyStatus.DEGRADED
        elif sharpe_approx < t.degraded_sharpe:
            reasons.append(f"negative Sharpe ({sharpe_approx:.2f}) → DEGRADED")
            recommended = StrategyStatus.DEGRADED

        # --- WATCH checks ---
        elif backtest_expectancy and backtest_expectancy > 0:
            drop = (backtest_expectancy - expectancy) / backtest_expectancy
            if drop > t.watch_expectancy_drop_pct:
                reasons.append(f"expectancy dropped {drop:.0%} from backtest → WATCH")
                recommended = StrategyStatus.WATCH
        elif backtest_win_rate and backtest_win_rate > 0:
            wr_drop = (backtest_win_rate - win_rate) / backtest_win_rate
            if wr_drop > t.watch_win_rate_drop_pct:
                reasons.append(f"win rate dropped {wr_drop:.0%} from backtest → WATCH")
                recommended = StrategyStatus.WATCH

        # Live vs backtest divergence
        if backtest_sharpe is not None and backtest_sharpe > 0:
            divergence = (backtest_sharpe - sharpe_approx) / backtest_sharpe
            metrics["live_backtest_divergence"] = round(divergence, 4)
            if divergence > t.max_live_backtest_divergence and recommended.value not in (
                    "SUSPENDED", "RETIRED"):
                reasons.append(f"live/backtest divergence {divergence:.0%} → DEGRADED")
                recommended = StrategyStatus.DEGRADED

        if not reasons:
            reasons.append("performance_acceptable")
            # If currently degraded/suspended but now performing well, suggest WATCH
            if current_status in (StrategyStatus.DEGRADED, StrategyStatus.SUSPENDED):
                recommended = StrategyStatus.WATCH
                reasons.append("recovery detected → WATCH")

        report = DegradationReport(strategy_name, current_status, recommended,
                                    reasons, metrics)
        if report.should_change:
            log.warning("strategy_degradation_detected",
                        strategy=strategy_name,
                        from_status=current_status.value,
                        to_status=recommended.value,
                        reasons=reasons)
        return report
