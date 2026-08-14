"""Agent 7 — Execution Agent. Confirms execution readiness."""
from __future__ import annotations

from typing import Any, Dict

from agents.agent_base import AgentDecision, BaseAgent


class ExecutionAgent(BaseAgent):
    name = "execution_agent"

    def evaluate(self, context: Dict[str, Any]) -> AgentDecision:
        if not context.get("trading_allowed", False):
            return self._decision(False, 1.0, reason="trading_not_allowed")
        qty = float(context.get("quantity", 0))
        approve = qty > 0
        return self._decision(approve, 0.7 if approve else 0.0,
                              reason=f"quantity={qty}")
