"""Agent 3 — News Analyst. Blocks trades during adverse/high-impact news."""
from __future__ import annotations

from typing import Any, Dict

from agents.agent_base import AgentDecision, BaseAgent


class NewsAnalystAgent(BaseAgent):
    name = "news_analyst"

    def evaluate(self, context: Dict[str, Any]) -> AgentDecision:
        risk_state = context.get("news_risk_state", "normal")
        direction = context.get("direction")
        sentiment = context.get("news_sentiment", "neutral")
        if risk_state == "blackout":
            return self._decision(False, 0.9, reason="news_blackout_window")
        contra = (direction == "LONG" and sentiment == "bearish") or \
                 (direction == "SHORT" and sentiment == "bullish")
        if contra:
            return self._decision(False, 0.6, reason="news_contradicts_direction")
        return self._decision(True, 0.55, reason=f"news_ok:{risk_state}/{sentiment}")
