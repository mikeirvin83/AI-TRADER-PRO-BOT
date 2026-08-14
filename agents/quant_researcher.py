"""Agent 4 — Quant Researcher. Proposes/validates hypotheses (advisory)."""
from __future__ import annotations

from typing import Any, Dict

from agents.agent_base import AgentDecision, BaseAgent


class QuantResearcherAgent(BaseAgent):
    name = "quant_researcher"

    def evaluate(self, context: Dict[str, Any]) -> AgentDecision:
        score = float(context.get("signal_score", 0))
        approve = score >= context.get("min_score", 75)
        return self._decision(approve, min(1.0, score / 100.0),
                              reason=f"signal_score={score}")
