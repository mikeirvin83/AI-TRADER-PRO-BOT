"""Compare strategies on a common metric set."""
from __future__ import annotations

from typing import Dict, List

from backtesting.metrics import PerformanceMetrics


class StrategyComparator:
    RANK_METRICS = ("sharpe", "sortino", "profit_factor", "expectancy", "total_return")

    def compare(self, results: Dict[str, PerformanceMetrics]) -> List[Dict]:
        """Return strategies ranked by a composite score (higher is better)."""
        rows: List[Dict] = []
        for name, m in results.items():
            score = (
                0.35 * m.sharpe
                + 0.25 * m.sortino
                + 0.20 * min(m.profit_factor, 5.0)
                + 0.20 * m.total_return
                - 0.50 * m.max_drawdown
            )
            rows.append({"strategy": name, "composite_score": round(score, 4),
                         **m.to_dict()})
        rows.sort(key=lambda r: r["composite_score"], reverse=True)
        for i, r in enumerate(rows):
            r["rank"] = i + 1
        return rows
