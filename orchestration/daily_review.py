"""End-of-day self-review routine (Section 29).

Analyzes all trades, signals, risk events, and strategy performance for the
day. Answers the 10 daily review questions from the spec. Does NOT
automatically change live strategies based on one day of results.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np

from config.constants import StrategyStatus
from config.logging_config import get_logger
from memory.trade_memory import TradeMemory
from validation.strategy_degradation import StrategyDegradationMonitor, DegradationReport

log = get_logger(__name__)


class DailyReview:
    def __init__(self) -> None:
        self.memory = TradeMemory()
        self.degradation_monitor = StrategyDegradationMonitor()

    def run(
        self,
        portfolio_snapshot: Optional[Dict[str, Any]] = None,
        strategy_trade_map: Optional[Dict[str, List[float]]] = None,
        signals_generated: int = 0,
        signals_rejected: int = 0,
        risk_events: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Run the full daily review.

        Args:
            portfolio_snapshot: Current portfolio state dict.
            strategy_trade_map: {strategy_name: [pnl, pnl, ...]} for today.
            signals_generated: Total signals generated today.
            signals_rejected: Signals rejected by quality/risk filters.
            risk_events: Risk events that occurred today.
        """
        trades = self.memory.recent(limit=500)
        today = datetime.now(timezone.utc).date()

        wins = [t for t in trades if (t.get("pnl") or 0) > 0]
        losses = [t for t in trades if (t.get("pnl") or 0) < 0]
        flat = [t for t in trades if (t.get("pnl") or 0) == 0]
        total_pnl = sum(t.get("pnl") or 0 for t in trades)

        # Per-strategy breakdown
        by_strategy: Dict[str, Dict[str, Any]] = {}
        for t in trades:
            s = t.get("strategy", "unknown")
            if s not in by_strategy:
                by_strategy[s] = {"trades": 0, "pnl": 0.0, "wins": 0, "losses": 0}
            by_strategy[s]["trades"] += 1
            by_strategy[s]["pnl"] += t.get("pnl") or 0
            if (t.get("pnl") or 0) > 0:
                by_strategy[s]["wins"] += 1
            elif (t.get("pnl") or 0) < 0:
                by_strategy[s]["losses"] += 1

        # Per-regime breakdown
        by_regime: Dict[str, int] = {}
        for t in trades:
            r = t.get("regime", "unknown")
            by_regime[r] = by_regime.get(r, 0) + 1

        # Strategy degradation check
        degradation_alerts: List[Dict[str, Any]] = []
        if strategy_trade_map:
            for strat_name, pnls in strategy_trade_map.items():
                report = self.degradation_monitor.evaluate(
                    strat_name, StrategyStatus.ACTIVE, pnls)
                if report.should_change:
                    degradation_alerts.append({
                        "strategy": strat_name,
                        "current": report.current_status.value,
                        "recommended": report.recommended_status.value,
                        "reasons": report.reasons,
                    })

        # Slippage analysis
        slippage_values = [t.get("slippage", 0) for t in trades if t.get("slippage")]
        avg_slippage = float(np.mean(slippage_values)) if slippage_values else 0.0

        # The 10 daily review questions
        review_questions = {
            "1_what_worked": [s for s, d in by_strategy.items() if d["pnl"] > 0],
            "2_what_failed": [s for s, d in by_strategy.items() if d["pnl"] < 0],
            "3_why": "See per-strategy and per-regime breakdown",
            "4_failure_predictable": "Review regime and news environment for failed trades",
            "5_conditions_changed": bool(risk_events),
            "6_strategy_degraded": [a["strategy"] for a in degradation_alerts],
            "7_research_needed": [a["strategy"] for a in degradation_alerts
                                  if a["recommended"] in ("DEGRADED", "SUSPENDED")],
            "8_do_not_change": [s for s, d in by_strategy.items()
                               if d["pnl"] > 0 and d["wins"] > d["losses"]],
            "9_execution_divergence": avg_slippage > 0.001,  # > 10bps average slippage
            "10_eligible_for_testing": [],  # populated by research engine
        }

        summary = {
            "date": today.isoformat(),
            "n_trades": len(trades),
            "wins": len(wins),
            "losses": len(losses),
            "flat": len(flat),
            "win_rate": round(len(wins) / len(trades), 3) if trades else 0.0,
            "total_pnl": round(total_pnl, 2),
            "avg_slippage": round(avg_slippage, 6),
            "signals_generated": signals_generated,
            "signals_rejected": signals_rejected,
            "signal_conversion_rate": round(len(trades) / max(signals_generated, 1), 3),
            "by_strategy": by_strategy,
            "by_regime": by_regime,
            "degradation_alerts": degradation_alerts,
            "risk_events_count": len(risk_events or []),
            "portfolio": portfolio_snapshot or {},
            "review_questions": review_questions,
        }

        log.info("daily_review", trades=len(trades), pnl=round(total_pnl, 2),
                 degradation_alerts=len(degradation_alerts))
        return summary
