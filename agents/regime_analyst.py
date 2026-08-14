"""Agent 2 — Regime Analyst. Confirms the signal fits the current regime."""
from __future__ import annotations

from typing import Any, Dict

from agents.agent_base import AgentDecision, BaseAgent


class RegimeAnalystAgent(BaseAgent):
    name = "regime_analyst"

    def evaluate(self, context: Dict[str, Any]) -> AgentDecision:
        regime = context.get("regime")
        allowed = context.get("allowed_regimes") or []
        if not allowed or regime is None:
            return self._decision(True, 0.5, reason="no_regime_restriction")
        fits = regime in allowed
        return self._decision(fits, 0.7 if fits else 0.2,
                              reason=f"regime={regime} fits={fits}")
