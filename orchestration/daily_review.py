"""End-of-day self-review routine."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from config.logging_config import get_logger
from memory.trade_memory import TradeMemory

log = get_logger(__name__)


class DailyReview:
    def __init__(self) -> None:
        self.memory = TradeMemory()

    def run(self) -> Dict[str, Any]:
        trades = self.memory.recent(limit=500)
        today = datetime.now(timezone.utc).date()
        wins = [t for t in trades if (t.get("pnl") or 0) > 0]
        losses = [t for t in trades if (t.get("pnl") or 0) < 0]
        total_pnl = sum(t.get("pnl") or 0 for t in trades)
        summary = {
            "date": today.isoformat(),
            "n_trades": len(trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(len(wins) / len(trades), 3) if trades else 0.0,
            "total_pnl": round(total_pnl, 2),
        }
        log.info("daily_review", **summary)
        return summary
