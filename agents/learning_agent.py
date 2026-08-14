"""Agent 9 — Learning Agent. Proposes controlled adjustments (advisory)."""
from __future__ import annotations

from typing import Any, Dict

from agents.agent_base import AgentDecision, BaseAgent


class LearningAgent(BaseAgent):
    name = "learning_agent"

    def evaluate(self, context: Dict[str, Any]) -> AgentDecision:
        # Never auto-applies changes; only flags that a review is warranted.
        recent_losses = int(context.get("recent_consecutive_losses", 0))
        propose = recent_losses >= 5
        return self._decision(True, 0.5, reason=("propose_review" if propose else "no_action"),
                              propose_review=propose)
