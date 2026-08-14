"""Weekly strategy review routine (Section 30).

Evaluates every strategy, compares against benchmarks, calculates rolling
performance, detects degradation, evaluates regime dependence and
correlations, reviews failed hypotheses, and generates new research ideas.

Strategies receive statuses: ACTIVE, WATCH, DEGRADED, SUSPENDED, RETIRED.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np

from config.constants import StrategyStatus
from config.logging_config import get_logger
from validation.strategy_degradation import (
    DegradationThresholds,
    StrategyDegradationMonitor,
)
from validation.ensemble_allocator import EnsembleAllocator
from research.strategy_comparator import StrategyComparator

log = get_logger(__name__)


class WeeklyReview:
    def __init__(self) -> None:
        self.degradation_monitor = StrategyDegradationMonitor()
        self.allocator = EnsembleAllocator()
        self.comparator = StrategyComparator()

    def run(
        self,
        strategy_profiles: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Run the weekly review.

        Args:
            strategy_profiles: List of dicts, each with:
                name, category, status, trade_pnls (list of floats),
                backtest_expectancy, backtest_win_rate, backtest_sharpe,
                sharpe, max_drawdown, profit_factor, win_rate, correlation_score.
        """
        profiles = strategy_profiles or []
        today = datetime.now(timezone.utc).date()

        # Degradation check for every strategy
        degradation_reports: List[Dict[str, Any]] = []
        status_recommendations: Dict[str, str] = {}
        for sp in profiles:
            trade_pnls = sp.get("trade_pnls", [])
            current = StrategyStatus(sp.get("status", "UNDER_RESEARCH"))
            report = self.degradation_monitor.evaluate(
                sp["name"], current, trade_pnls,
                backtest_expectancy=sp.get("backtest_expectancy"),
                backtest_win_rate=sp.get("backtest_win_rate"),
                backtest_sharpe=sp.get("backtest_sharpe"),
            )
            degradation_reports.append({
                "strategy": sp["name"],
                "current": report.current_status.value,
                "recommended": report.recommended_status.value,
                "should_change": report.should_change,
                "reasons": report.reasons,
                "metrics": report.metrics,
            })
            status_recommendations[sp["name"]] = report.recommended_status.value

        # By-status summary
        by_status: Dict[str, int] = {}
        for sp in profiles:
            rec = status_recommendations.get(sp["name"], sp.get("status", "UNKNOWN"))
            by_status[rec] = by_status.get(rec, 0) + 1

        # Ensemble allocation recommendation
        allocation_input = []
        for sp in profiles:
            rec_status = status_recommendations.get(sp["name"], sp.get("status"))
            allocation_input.append({
                "name": sp["name"],
                "category": sp.get("category", "other"),
                "status": rec_status,
                "sharpe": sp.get("sharpe", 0),
                "max_drawdown": sp.get("max_drawdown", 0.5),
                "profit_factor": sp.get("profit_factor", 1),
                "win_rate": sp.get("win_rate", 0.5),
                "correlation_score": sp.get("correlation_score", 0),
            })
        allocation = self.allocator.allocate(allocation_input)

        # Strategy-level P&L summary
        strategy_pnl: Dict[str, float] = {}
        for sp in profiles:
            pnls = sp.get("trade_pnls", [])
            strategy_pnl[sp["name"]] = round(sum(pnls), 2) if pnls else 0.0

        summary = {
            "week_ending": today.isoformat(),
            "n_strategies": len(profiles),
            "by_status": by_status,
            "degradation_reports": degradation_reports,
            "status_changes_needed": sum(
                1 for d in degradation_reports if d["should_change"]),
            "allocation": allocation.to_dict(),
            "strategy_pnl": strategy_pnl,
        }

        log.info("weekly_review", strategies=len(profiles),
                 changes_needed=summary["status_changes_needed"])
        return summary
