"""Base agent class.

Agents are cooperating specialists in the decision loop. Two agents hold VETO
authority (risk_manager, strategy_governor): if either vetoes, the action is
blocked regardless of other agents' votes.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from config.logging_config import get_logger


@dataclass
class AgentDecision:
    agent: str
    approve: bool
    confidence: float = 0.0
    veto: bool = False
    reason: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class BaseAgent(abc.ABC):
    name: str = "base_agent"
    has_veto: bool = False

    def __init__(self) -> None:
        self.log = get_logger(self.name)

    @abc.abstractmethod
    def evaluate(self, context: Dict[str, Any]) -> AgentDecision:
        """Inspect the shared context and return a decision."""
        raise NotImplementedError

    def _decision(self, approve: bool, confidence: float = 0.5, veto: bool = False,
                  reason: str = "", **data: Any) -> AgentDecision:
        return AgentDecision(self.name, approve, confidence, veto, reason, data)
