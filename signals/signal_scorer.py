"""Signal scorer — unified 0-100 quality score.

Combines weighted components (trend alignment, momentum, volume confirmation,
risk/reward, regime fit, news posture) into a single score and classifies it
against the configured thresholds.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional

from config.settings import Settings, get_settings


class SignalQuality(str, Enum):
    REJECTED = "REJECTED"
    QUALIFIED = "QUALIFIED"
    HIGH_QUALITY = "HIGH_QUALITY"


# Component weights (sum to 1.0).
DEFAULT_WEIGHTS: Dict[str, float] = {
    "trend": 0.25,
    "momentum": 0.20,
    "volume": 0.15,
    "risk_reward": 0.20,
    "regime": 0.10,
    "news": 0.10,
}


@dataclass
class ScoreBreakdown:
    total: float
    quality: SignalQuality
    components: Dict[str, float]


class SignalScorer:
    def __init__(self, settings: Optional[Settings] = None, weights: Optional[Dict[str, float]] = None) -> None:
        self.settings = settings or get_settings()
        self.weights = weights or DEFAULT_WEIGHTS

    def score(self, components: Dict[str, float]) -> ScoreBreakdown:
        """Compute the weighted score. Each component is expected in [0, 100]."""
        total = 0.0
        used: Dict[str, float] = {}
        for name, weight in self.weights.items():
            val = float(components.get(name, 0.0))
            val = max(0.0, min(100.0, val))
            used[name] = val
            total += weight * val
        total = round(total, 2)
        return ScoreBreakdown(total, self.classify(total), used)

    def classify(self, total: float) -> SignalQuality:
        if total >= self.settings.SIGNAL_SCORE_MIN_HIGH_QUALITY:
            return SignalQuality.HIGH_QUALITY
        if total >= self.settings.SIGNAL_SCORE_MIN_QUALIFIED:
            return SignalQuality.QUALIFIED
        return SignalQuality.REJECTED

    def is_qualified(self, total: float) -> bool:
        return total >= self.settings.SIGNAL_SCORE_MIN_QUALIFIED
