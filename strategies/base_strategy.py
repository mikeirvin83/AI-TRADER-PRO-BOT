"""Abstract base strategy.

Enforces the strategy contract: every concrete strategy declares its metadata
and implements :meth:`generate_signal`. A strategy MUST refuse to emit a signal
unless every required field (asset, direction, entry, stop, target,
invalidation condition, expiration) is present — no partial signals.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd

from config.constants import MarketRegime, SignalDirection, StrategyStatus
from config.logging_config import get_logger

log = get_logger(__name__)


class SignalValidationError(ValueError):
    """Raised when a strategy tries to build a signal missing required fields."""


@dataclass
class StrategySignal:
    """A complete, self-describing trade signal."""

    asset: str
    direction: SignalDirection
    entry: float
    stop: float
    target: float
    invalidation_condition: str
    expiration_time: datetime
    strategy_name: str
    timeframe: str = ""
    score: float = 0.0
    regime: Optional[str] = None
    news_environment: Optional[str] = None
    rationale: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    REQUIRED = ("asset", "direction", "entry", "stop", "target",
                "invalidation_condition", "expiration_time")

    def __post_init__(self) -> None:
        missing = []
        for f in self.REQUIRED:
            v = getattr(self, f)
            if v is None or (isinstance(v, str) and not v.strip()):
                missing.append(f)
        if missing:
            raise SignalValidationError(f"Signal missing required fields: {missing}")
        # sanity: stop must be on the correct side of entry
        if self.direction == SignalDirection.LONG and not (self.stop < self.entry < self.target):
            raise SignalValidationError("LONG signal requires stop < entry < target")
        if self.direction == SignalDirection.SHORT and not (self.stop > self.entry > self.target):
            raise SignalValidationError("SHORT signal requires stop > entry > target")

    @property
    def risk_reward(self) -> float:
        risk = abs(self.entry - self.stop)
        reward = abs(self.target - self.entry)
        return reward / risk if risk > 0 else 0.0


class BaseStrategy(abc.ABC):
    """Abstract base every concrete strategy inherits from."""

    name: str = "base"
    version: str = "0.1.0"                       # semver
    status: StrategyStatus = StrategyStatus.UNDER_RESEARCH
    allowed_regimes: List[MarketRegime] = []
    min_signal_score: int = 75
    category: str = "generic"

    def __init__(self, params: Optional[Dict[str, Any]] = None) -> None:
        self.params = params or {}

    @abc.abstractmethod
    def generate_signal(
        self,
        data: pd.DataFrame,
        features: pd.DataFrame,
        regime: Optional[MarketRegime] = None,
        news: Optional[Dict[str, Any]] = None,
    ) -> Optional[StrategySignal]:
        """Return a StrategySignal or None. Never return a partial signal."""
        raise NotImplementedError

    # ------------------------------------------------------------------ #
    def is_regime_allowed(self, regime: Optional[MarketRegime]) -> bool:
        if not self.allowed_regimes:
            return True
        return regime in self.allowed_regimes if regime else False

    def _last(self, features: pd.DataFrame, col: str) -> Optional[float]:
        if col not in features.columns or features[col].dropna().empty:
            return None
        return float(features[col].dropna().iloc[-1])

    def describe(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "status": self.status.value,
            "category": self.category,
            "allowed_regimes": [r.value for r in self.allowed_regimes],
            "min_signal_score": self.min_signal_score,
            "params": self.params,
        }
