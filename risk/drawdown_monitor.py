"""Real-time drawdown tracking against a running equity high-water mark."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Tuple

from config.logging_config import get_logger

log = get_logger(__name__)


@dataclass
class DrawdownMonitor:
    peak_equity: float = 0.0
    current_equity: float = 0.0
    _series: List[Tuple[datetime, float]] = field(default_factory=list)

    def update(self, equity: float) -> float:
        """Record equity, update peak, return current drawdown fraction (>=0)."""
        self.current_equity = equity
        self.peak_equity = max(self.peak_equity, equity)
        self._series.append((datetime.now(timezone.utc), equity))
        return self.current_drawdown

    @property
    def current_drawdown(self) -> float:
        if self.peak_equity <= 0:
            return 0.0
        return max(0.0, (self.peak_equity - self.current_equity) / self.peak_equity)

    def max_drawdown(self) -> float:
        peak, mdd = 0.0, 0.0
        for _, eq in self._series:
            peak = max(peak, eq)
            if peak > 0:
                mdd = max(mdd, (peak - eq) / peak)
        return mdd

    def reset(self) -> None:
        self.peak_equity = self.current_equity
        self._series.clear()
