"""Agent 10 — Strategy Governor. VETO authority over strategy participation."""
from __future__ import annotations

from typing import Any, Dict

from agents.agent_base import AgentDecision, BaseAgent


class StrategyGovernorAgent(BaseAgent):
    name = "strategy_governor"
    has_veto = True

    def evaluate(self, context: Dict[str, Any]) -> AgentDecision:
        status = context.get("strategy_status", "UNDER_RESEARCH")
        # Only ACTIVE (and WATCH) strategies may trade; others are vetoed.
        if status not in ("ACTIVE", "WATCH"):
            return self._decision(False, 1.0, veto=True,
                                  reason=f"strategy_not_approved:{status}")
        return self._decision(True, 0.9, reason=f"strategy_status_ok:{status}")
