"""Agent 6 — Risk Manager. VETO authority over any trade."""
from __future__ import annotations

from typing import Any, Dict

from agents.agent_base import AgentDecision, BaseAgent


class RiskManagerAgent(BaseAgent):
    name = "risk_manager"
    has_veto = True

    def evaluate(self, context: Dict[str, Any]) -> AgentDecision:
        decision = context.get("risk_decision")
        # risk_decision is a RiskDecision-like dict {allowed, reason}
        allowed = bool(decision.get("allowed", False)) if isinstance(decision, dict) else False
        reason = decision.get("reason", "no_risk_decision") if isinstance(decision, dict) else "no_risk_decision"
        if not allowed:
            return self._decision(False, 1.0, veto=True, reason=f"risk_veto:{reason}")
        return self._decision(True, 0.9, reason="risk_ok")
