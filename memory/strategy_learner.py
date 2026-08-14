"""Strategy learning loop — closes the feedback loop from outcomes to proposals.

Analyses completed trade outcomes and strategy performance to generate
improvement proposals. ALL proposals go through the LearningEngine
approval pipeline — nothing is applied automatically.

This is the "self-improving" mechanism per the spec: the system proposes
parameter changes, regime adjustments, and strategy lifecycle transitions
based on evidence, but a human or the strategy governor must approve.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np

from config.constants import StrategyStatus, TRADING_DAYS_PER_YEAR
from config.logging_config import get_logger
from memory.learning_engine import LearningEngine
from memory.knowledge_store import KnowledgeStore
from memory.llm_analyzer import LLMAnalyzer

log = get_logger(__name__)


class StrategyLearner:
    """Analyses strategy outcomes and proposes improvements.

    Operates on three levels:
    1. Statistical analysis — deterministic metrics-based checks
    2. Pattern detection — identifying recurring scenarios
    3. LLM-assisted analysis — deeper insight generation (optional)

    All outputs are *proposals* in the LearningEngine, never direct mutations.
    """

    def __init__(self) -> None:
        self.learning_engine = LearningEngine()
        self.knowledge_store = KnowledgeStore()
        self.llm = LLMAnalyzer()

    # ------------------------------------------------------------------ #
    # Main analysis entry point
    # ------------------------------------------------------------------ #

    def analyze_and_propose(
        self,
        strategy_name: str,
        trade_pnls: List[float],
        strategy_params: Dict[str, Any],
        regime_distribution: Optional[Dict[str, int]] = None,
        backtest_metrics: Optional[Dict[str, float]] = None,
    ) -> List[Dict[str, Any]]:
        """Run full analysis and return list of proposals generated."""
        proposals: List[Dict[str, Any]] = []

        if len(trade_pnls) < 10:
            log.info("strategy_learner_skip", strategy=strategy_name,
                     reason="insufficient_trades", n=len(trade_pnls))
            return proposals

        # 1. Statistical analysis
        stats = self._compute_statistics(trade_pnls)

        # 2. Check for drift from backtest
        if backtest_metrics:
            drift = self._detect_drift(stats, backtest_metrics)
            if drift:
                pid = self.learning_engine.propose_change(
                    event_type="performance_drift",
                    description=(
                        f"Strategy '{strategy_name}' shows drift from backtest: "
                        f"{', '.join(drift['reasons'])}"
                    ),
                    before=backtest_metrics,
                    after=stats,
                )
                proposals.append({"id": pid, "type": "drift", **drift})

        # 3. Regime suitability analysis
        if regime_distribution:
            regime_insight = self._analyze_regime_fit(
                strategy_name, regime_distribution, trade_pnls)
            if regime_insight:
                pid = self.learning_engine.propose_change(
                    event_type="regime_adjustment",
                    description=(
                        f"Strategy '{strategy_name}' regime suitability update: "
                        f"{regime_insight['recommendation']}"
                    ),
                    before={"current_regimes": "all"},
                    after=regime_insight,
                )
                proposals.append({"id": pid, "type": "regime", **regime_insight})

        # 4. Parameter adjustment suggestions (statistical)
        param_suggestions = self._suggest_parameters(stats, strategy_params)
        if param_suggestions:
            pid = self.learning_engine.propose_change(
                event_type="parameter_adjustment",
                description=(
                    f"Strategy '{strategy_name}' parameter suggestions: "
                    f"{list(param_suggestions.keys())}"
                ),
                before=strategy_params,
                after={**strategy_params, **param_suggestions},
            )
            proposals.append({"id": pid, "type": "params", "changes": param_suggestions})

        # 5. Persist learned knowledge
        self._update_knowledge(strategy_name, stats, regime_distribution)

        log.info("strategy_learner_complete", strategy=strategy_name,
                 proposals=len(proposals), trades=len(trade_pnls))
        return proposals

    # ------------------------------------------------------------------ #
    # LLM-powered deep analysis (optional, runs when LLM available)
    # ------------------------------------------------------------------ #

    def deep_analysis(
        self,
        strategy_name: str,
        trades: List[Dict[str, Any]],
        metrics: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Run LLM-powered analysis and return insights.

        Does not create proposals automatically — returns insights for
        review by the operator or the strategy governor.
        """
        if not self.llm.available:
            return None

        evaluation = self.llm.evaluate_strategy_performance(
            strategy_name, metrics, trades)
        patterns = self.llm.detect_patterns(trades)

        return {
            "strategy": strategy_name,
            "evaluation": evaluation,
            "patterns": patterns,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------ #
    # Statistical helpers
    # ------------------------------------------------------------------ #

    def _compute_statistics(self, pnls: List[float]) -> Dict[str, float]:
        """Compute comprehensive trade statistics."""
        arr = np.array(pnls)
        wins = arr[arr > 0]
        losses = arr[arr < 0]

        cum = np.cumsum(arr)
        peak = np.maximum.accumulate(cum)
        dd = peak - cum
        max_dd = float(dd.max()) if len(dd) > 0 else 0.0

        avg_win = float(wins.mean()) if len(wins) > 0 else 0.0
        avg_loss = float(losses.mean()) if len(losses) > 0 else 0.0

        return {
            "n_trades": len(pnls),
            "win_rate": float(len(wins) / len(arr)) if len(arr) > 0 else 0.0,
            "avg_pnl": float(arr.mean()),
            "total_pnl": float(arr.sum()),
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": (
                float(wins.sum() / abs(losses.sum()))
                if len(losses) > 0 and losses.sum() != 0
                else float("inf") if len(wins) > 0 else 0.0
            ),
            "max_drawdown": max_dd,
            "expectancy": float(arr.mean()),
            "std_pnl": float(arr.std()) if len(arr) > 1 else 0.0,
            "sharpe": (
                float(arr.mean() / arr.std() * np.sqrt(TRADING_DAYS_PER_YEAR))
                if len(arr) > 1 and arr.std() > 0 else 0.0
            ),
            "max_consecutive_losses": self._max_consecutive(arr, negative=True),
            "max_consecutive_wins": self._max_consecutive(arr, negative=False),
        }

    @staticmethod
    def _max_consecutive(arr: np.ndarray, negative: bool) -> int:
        """Count max consecutive wins or losses."""
        mask = arr < 0 if negative else arr > 0
        max_run = 0
        current = 0
        for val in mask:
            if val:
                current += 1
                max_run = max(max_run, current)
            else:
                current = 0
        return max_run

    def _detect_drift(
        self, live_stats: Dict[str, float],
        backtest_stats: Dict[str, float],
    ) -> Optional[Dict[str, Any]]:
        """Detect significant drift between live and backtest performance."""
        reasons: List[str] = []

        # Win rate drift > 10%
        bt_wr = backtest_stats.get("win_rate", 0.5)
        live_wr = live_stats.get("win_rate", 0.5)
        if bt_wr > 0 and abs(live_wr - bt_wr) / bt_wr > 0.1:
            reasons.append(f"win_rate: backtest={bt_wr:.2%} vs live={live_wr:.2%}")

        # Sharpe drift > 30%
        bt_sharpe = backtest_stats.get("sharpe", 0)
        live_sharpe = live_stats.get("sharpe", 0)
        if bt_sharpe > 0 and live_sharpe < bt_sharpe * 0.7:
            reasons.append(f"sharpe: backtest={bt_sharpe:.2f} vs live={live_sharpe:.2f}")

        # Profit factor drift
        bt_pf = backtest_stats.get("profit_factor", 1)
        live_pf = live_stats.get("profit_factor", 1)
        if bt_pf > 1 and live_pf < bt_pf * 0.7:
            reasons.append(f"profit_factor: backtest={bt_pf:.2f} vs live={live_pf:.2f}")

        # Drawdown exceeded
        bt_dd = backtest_stats.get("max_drawdown", 0)
        live_dd = live_stats.get("max_drawdown", 0)
        if bt_dd > 0 and live_dd > bt_dd * 1.5:
            reasons.append(f"max_drawdown: backtest={bt_dd:.0f} vs live={live_dd:.0f}")

        if not reasons:
            return None
        return {
            "severity": "high" if len(reasons) >= 3 else "medium",
            "reasons": reasons,
            "live_stats": live_stats,
            "backtest_stats": backtest_stats,
        }

    def _analyze_regime_fit(
        self,
        strategy_name: str,
        regime_distribution: Dict[str, int],
        trade_pnls: List[float],
    ) -> Optional[Dict[str, Any]]:
        """Analyse which regimes the strategy performs best/worst in."""
        # This is a simplified version — in production, trades would be
        # tagged with their regime for per-regime P&L calculation
        total_trades = sum(regime_distribution.values())
        if total_trades < 20:
            return None

        dominant = max(regime_distribution, key=regime_distribution.get)  # type: ignore
        dominant_pct = regime_distribution[dominant] / total_trades

        # If > 70% of trades in one regime, suggest focusing there
        if dominant_pct > 0.7:
            return {
                "recommendation": f"Strategy heavily concentrated in {dominant} regime ({dominant_pct:.0%})",
                "dominant_regime": dominant,
                "distribution": regime_distribution,
                "suggested_regimes": [dominant],
            }
        return None

    def _suggest_parameters(
        self,
        stats: Dict[str, float],
        current_params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Suggest parameter adjustments based on statistics."""
        suggestions: Dict[str, Any] = {}

        # If win rate is very low, suggest tightening entry criteria
        if stats["win_rate"] < 0.3:
            current_min_score = current_params.get("min_signal_score", 75)
            suggestions["min_signal_score"] = min(95, current_min_score + 5)

        # If consecutive losses are high, suggest position sizing reduction
        if stats["max_consecutive_losses"] >= 8:
            current_risk = current_params.get("risk_per_trade_pct", 0.01)
            suggestions["risk_per_trade_pct"] = max(0.005, current_risk * 0.8)

        # If profit factor is weak, suggest tighter stop-loss
        if 0 < stats["profit_factor"] < 1.1:
            current_sl = current_params.get("stop_loss_atr_mult", 2.0)
            suggestions["stop_loss_atr_mult"] = max(1.0, current_sl * 0.9)

        return suggestions

    def _update_knowledge(
        self,
        strategy_name: str,
        stats: Dict[str, float],
        regime_dist: Optional[Dict[str, int]],
    ) -> None:
        """Persist learned knowledge about the strategy."""
        try:
            self.knowledge_store.remember(
                key=f"strategy_stats:{strategy_name}",
                content={
                    "stats": stats,
                    "regime_distribution": regime_dist or {},
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                },
                category="strategy_performance",
                confidence=min(1.0, stats["n_trades"] / 100),
            )
        except Exception:  # noqa: BLE001
            # Knowledge store may not have DB; don't break the learner
            log.debug("knowledge_store_write_skipped", strategy=strategy_name)
