"""Agent 8 — Trade Reviewer. Post-trade analysis (advisory, not gating)."""
from __future__ import annotations

from typing import Any, Dict

from agents.agent_base import AgentDecision, BaseAgent


class TradeReviewerAgent(BaseAgent):
    name = "trade_reviewer"

    def evaluate(self, context: Dict[str, Any]) -> AgentDecision:
        trade = context.get("closed_trade", {})
        pnl = float(trade.get("pnl", 0))
        note = "win" if pnl > 0 else ("loss" if pnl < 0 else "scratch")
        return self._decision(True, 0.5, reason=f"reviewed:{note}", pnl=pnl)
