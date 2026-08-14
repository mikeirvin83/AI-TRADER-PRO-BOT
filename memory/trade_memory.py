"""Per-trade memory with full decision context for later review/learning."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from config.logging_config import get_logger
from database.models import Trade
from database.repositories.trades import TradeRepository
from database.session import session_scope

log = get_logger(__name__)


class TradeMemory:
    def record_trade(self, trade_fields: Dict[str, Any]) -> str:
        """Persist a completed trade with its full context payload."""
        with session_scope() as s:
            repo = TradeRepository(s)
            trade = Trade(**trade_fields)
            repo.add(trade)
            log.info("trade_recorded", symbol=trade.symbol, pnl=trade_fields.get("pnl"))
            return str(trade.id)

    def recent(self, limit: int = 100) -> List[Dict[str, Any]]:
        with session_scope() as s:
            rows = TradeRepository(s).closed_trades(limit)
            return [{"symbol": r.symbol, "direction": r.direction, "pnl": float(r.pnl or 0),
                     "r_multiple": r.r_multiple, "regime": r.regime,
                     "exit_reason": r.exit_reason} for r in rows]
