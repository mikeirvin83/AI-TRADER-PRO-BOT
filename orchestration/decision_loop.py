"""Main event-driven decision loop.

Coordinates the agents to reach a trade decision. VETO agents (risk_manager,
strategy_governor) can unilaterally block a trade. All other agents contribute
weighted approval; a trade proceeds only if no veto and aggregate approval
clears the configured threshold.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from config.logging_config import get_logger
from agents.agent_base import AgentDecision, BaseAgent
from agents.backtesting_agent import BacktestingAgent
from agents.execution_agent import ExecutionAgent
from agents.learning_agent import LearningAgent
from agents.market_scanner import MarketScannerAgent
from agents.news_analyst import NewsAnalystAgent
from agents.quant_researcher import QuantResearcherAgent
from agents.regime_analyst import RegimeAnalystAgent
from agents.risk_manager import RiskManagerAgent
from agents.strategy_governor import StrategyGovernorAgent
from agents.trade_reviewer import TradeReviewerAgent

log = get_logger(__name__)


@dataclass
class LoopDecision:
    approved: bool
    vetoed_by: List[str] = field(default_factory=list)
    approval_score: float = 0.0
    agent_decisions: List[AgentDecision] = field(default_factory=list)
    reason: str = ""


class DecisionLoop:
    def __init__(self, approval_threshold: float = 0.5) -> None:
        self.approval_threshold = approval_threshold
        self.gating_agents: List[BaseAgent] = [
            MarketScannerAgent(), RegimeAnalystAgent(), NewsAnalystAgent(),
            QuantResearcherAgent(), BacktestingAgent(), RiskManagerAgent(),
            ExecutionAgent(), StrategyGovernorAgent(),
        ]
        self.review_agents: List[BaseAgent] = [TradeReviewerAgent(), LearningAgent()]

    def decide(self, context: Dict[str, Any]) -> LoopDecision:
        decisions: List[AgentDecision] = []
        vetoed_by: List[str] = []
        approvals: List[float] = []

        for agent in self.gating_agents:
            d = agent.evaluate(context)
            decisions.append(d)
            if agent.has_veto and d.veto:
                vetoed_by.append(agent.name)
            approvals.append(d.confidence if d.approve else -d.confidence)

        if vetoed_by:
            log.info("decision_vetoed", vetoed_by=vetoed_by)
            return LoopDecision(False, vetoed_by, 0.0, decisions, f"veto:{vetoed_by}")

        score = sum(approvals) / len(approvals) if approvals else 0.0
        approved = score >= self.approval_threshold
        return LoopDecision(approved, [], round(score, 3), decisions,
                            "approved" if approved else "below_threshold")

    def review(self, context: Dict[str, Any]) -> List[AgentDecision]:
        return [a.evaluate(context) for a in self.review_agents]
