"""Order manager — order lifecycle, dedup and reconciliation.

Routes orders to the paper engine or the Alpaca executor based on the current
trading mode, prevents duplicate orders for the same symbol/direction, and
reconciles local order state against the broker.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from config.constants import OrderSide, OrderStatus, OrderType, SignalDirection
from config.logging_config import get_logger
from config.settings import TradingMode, get_settings
from core.system_state import get_system_state
from execution.alpaca_executor import AlpacaExecutor
from execution.paper_engine import PaperEngine

log = get_logger(__name__)


@dataclass
class OrderTicket:
    symbol: str
    side: str
    qty: float
    order_type: str = OrderType.MARKET.value
    limit_price: Optional[float] = None
    strategy_name: Optional[str] = None
    client_order_id: str = ""
    status: str = OrderStatus.PENDING.value
    broker_order_id: Optional[str] = None
    mode: str = TradingMode.PAPER.value


class DuplicateOrderError(RuntimeError):
    pass


class OrderManager:
    def __init__(
        self,
        paper_engine: Optional[PaperEngine] = None,
        executor: Optional[AlpacaExecutor] = None,
    ) -> None:
        self.settings = get_settings()
        self.state = get_system_state()
        self.paper = paper_engine or PaperEngine()
        self.executor = executor or AlpacaExecutor()
        self._open: Dict[str, OrderTicket] = {}   # client_order_id -> ticket

    # ------------------------------------------------------------------ #
    def _direction_to_side(self, direction: SignalDirection) -> str:
        return OrderSide.BUY.value if direction == SignalDirection.LONG else OrderSide.SELL.value

    def _has_duplicate(self, symbol: str, side: str) -> bool:
        for t in self._open.values():
            if t.symbol == symbol and t.side == side and t.status in (
                OrderStatus.PENDING.value, OrderStatus.SUBMITTED.value,
                OrderStatus.PARTIALLY_FILLED.value,
            ):
                return True
        return False

    # ------------------------------------------------------------------ #
    def place_order(
        self,
        signal: Dict[str, Any],
        next_open_price: Optional[float] = None,
    ) -> OrderTicket:
        """Route an order based on mode. ``signal`` needs symbol/direction/qty/entry.

        For PAPER mode a ``next_open_price`` (next bar open) is used to fill so we
        never look ahead within the current bar.
        """
        mode = self.state.get_mode()
        if not self.state.is_trading_allowed():
            raise RuntimeError(f"trading_not_allowed_in_mode:{mode.value}")

        symbol = signal["symbol"]
        direction = signal["direction"]
        if isinstance(direction, str):
            direction = SignalDirection(direction)
        side = self._direction_to_side(direction)
        qty = float(signal["qty"])

        if self._has_duplicate(symbol, side):
            raise DuplicateOrderError(f"duplicate_order:{symbol}:{side}")

        ticket = OrderTicket(
            symbol=symbol, side=side, qty=qty,
            order_type=signal.get("order_type", OrderType.MARKET.value),
            limit_price=signal.get("limit_price"),
            strategy_name=signal.get("strategy_name"),
            client_order_id=str(uuid.uuid4()),
            mode=mode.value,
        )
        self._open[ticket.client_order_id] = ticket

        if mode == TradingMode.PAPER:
            fill_price = next_open_price if next_open_price is not None else float(signal["entry"])
            self.paper.fill_order(symbol, side, qty, fill_price, volume=signal.get("volume"))
            ticket.status = OrderStatus.FILLED.value
        else:  # SHADOW / LIVE
            result = self.executor.submit(symbol, side, qty, ticket.order_type, ticket.limit_price)
            ticket.broker_order_id = result.broker_order_id
            ticket.status = OrderStatus.SUBMITTED.value if result.accepted else OrderStatus.REJECTED.value

        log.info("order_placed", symbol=symbol, side=side, qty=qty,
                 mode=mode.value, status=ticket.status)
        return ticket

    # ------------------------------------------------------------------ #
    def reconcile(self) -> Dict[str, Any]:
        """Compare local open orders against the broker (LIVE/SHADOW only)."""
        summary: Dict[str, Any] = {"local_open": len(self._open), "broker_open": 0, "discrepancies": []}
        if self.state.get_mode() != TradingMode.LIVE or not self.executor.client.sdk_available:
            return summary
        try:
            broker_orders = self.executor.client.get_orders("open")
            summary["broker_open"] = len(broker_orders)
            broker_ids = {str(o.get("id")) for o in broker_orders}
            for t in self._open.values():
                if t.broker_order_id and t.broker_order_id not in broker_ids and \
                        t.status == OrderStatus.SUBMITTED.value:
                    summary["discrepancies"].append(t.client_order_id)
        except Exception:  # noqa: BLE001
            log.exception("reconcile_error")
        return summary

    def open_orders(self) -> List[OrderTicket]:
        return [t for t in self._open.values() if t.status in (
            OrderStatus.PENDING.value, OrderStatus.SUBMITTED.value,
            OrderStatus.PARTIALLY_FILLED.value,
        )]
