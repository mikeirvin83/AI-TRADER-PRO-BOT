"""Agent 5 — Backtesting Agent. Requires validated historical edge."""
from __future__ import annotations

from typing import Any, Dict

from agents.agent_base import AgentDecision, BaseAgent


class BacktestingAgent(BaseAgent):
    name = "backtesting_agent"

    def evaluate(self, context: Dict[str, Any]) -> AgentDecision:
        stats = context.get("strategy_backtest", {})
        sharpe = float(stats.get("sharpe", 0))
        pf = float(stats.get("profit_factor", 0))
        approve = sharpe >= 0.5 and pf >= 1.1
        return self._decision(approve, 0.6 if approve else 0.3,
                              reason=f"sharpe={sharpe},pf={pf}")
