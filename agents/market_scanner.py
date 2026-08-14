"""Agent 1 — Market Scanner. Surfaces candidate symbols from the universe."""
from __future__ import annotations

from typing import Any, Dict

from agents.agent_base import AgentDecision, BaseAgent


class MarketScannerAgent(BaseAgent):
    name = "market_scanner"

    def evaluate(self, context: Dict[str, Any]) -> AgentDecision:
        candidates = context.get("candidates", [])
        approve = len(candidates) > 0
        return self._decision(approve, confidence=0.6 if approve else 0.0,
                              reason=f"{len(candidates)} candidates", candidates=candidates)
