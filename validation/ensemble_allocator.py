"""Strategy Ensemble Allocator (Section 23).

Determines portfolio allocation across independent strategies based on
validated performance, current regime, correlation, drawdown, and robustness.

Allocation percentages are NEVER hardcoded — they are derived from evidence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from config.logging_config import get_logger

log = get_logger(__name__)


@dataclass
class StrategyAllocation:
    name: str
    category: str
    weight: float       # 0.0 – 1.0
    reason: str = ""


@dataclass
class EnsembleAllocationResult:
    allocations: List[StrategyAllocation] = field(default_factory=list)
    total_weight: float = 0.0
    unallocated: float = 0.0     # cash reserve

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allocations": [{"name": a.name, "category": a.category,
                             "weight": round(a.weight, 4), "reason": a.reason}
                            for a in self.allocations],
            "total_weight": round(self.total_weight, 4),
            "cash_reserve": round(self.unallocated, 4),
        }


class EnsembleAllocator:
    """Allocate portfolio weight across strategies using a score-weighted approach.

    Score = w1 * sharpe + w2 * (1 - max_dd) + w3 * profit_factor + w4 * win_rate
            - w5 * correlation_penalty

    Strategies with DEGRADED or worse status get zero weight.
    A minimum cash reserve is always maintained.
    """

    def __init__(
        self,
        min_cash_reserve: float = 0.10,   # Always keep 10% cash
        max_single_strategy_pct: float = 0.30,
        max_category_pct: float = 0.40,
    ) -> None:
        self.min_cash_reserve = min_cash_reserve
        self.max_single_strategy_pct = max_single_strategy_pct
        self.max_category_pct = max_category_pct

    def allocate(
        self,
        strategies: List[Dict[str, Any]],
    ) -> EnsembleAllocationResult:
        """Compute allocations.

        Each item in ``strategies`` must have:
            name, category, status, sharpe, max_drawdown, profit_factor, win_rate,
            correlation_score (0-1, higher = more correlated with rest of portfolio).
        """
        eligible = [s for s in strategies if s.get("status") in ("ACTIVE", "WATCH")]
        if not eligible:
            return EnsembleAllocationResult(unallocated=1.0)

        # Score each strategy
        scores: Dict[str, float] = {}
        for s in eligible:
            sharpe = max(0, float(s.get("sharpe", 0)))
            dd = float(s.get("max_drawdown", 0.5))
            pf = min(5.0, float(s.get("profit_factor", 1.0)))
            wr = float(s.get("win_rate", 0.5))
            corr_penalty = float(s.get("correlation_score", 0)) * 2

            score = 0.35 * sharpe + 0.25 * (1 - dd) + 0.20 * (pf / 5.0) + 0.20 * wr - corr_penalty
            scores[s["name"]] = max(0.001, score)  # floor to avoid zero division

        # Normalize to weights
        total_score = sum(scores.values())
        available = 1.0 - self.min_cash_reserve
        allocations: List[StrategyAllocation] = []
        category_totals: Dict[str, float] = {}

        for s in eligible:
            raw_weight = (scores[s["name"]] / total_score) * available
            # Cap single strategy
            weight = min(raw_weight, self.max_single_strategy_pct)

            # Cap category
            cat = s.get("category", "other")
            cat_used = category_totals.get(cat, 0)
            if cat_used + weight > self.max_category_pct:
                weight = max(0, self.max_category_pct - cat_used)

            category_totals[cat] = category_totals.get(cat, 0) + weight
            allocations.append(StrategyAllocation(
                name=s["name"],
                category=cat,
                weight=weight,
                reason=f"score={scores[s['name']]:.3f}",
            ))

        total_weight = sum(a.weight for a in allocations)
        unallocated = 1.0 - total_weight

        log.info("ensemble_allocation", n_strategies=len(allocations),
                 total_allocated=round(total_weight, 4),
                 cash_reserve=round(unallocated, 4))

        return EnsembleAllocationResult(allocations, total_weight, unallocated)
