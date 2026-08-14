"""Alpaca executor — live/shadow order routing.

* LIVE  : submits orders to Alpaca.
* SHADOW: computes and logs what WOULD be sent, without transmitting.
Both paths honour the master kill switch via :class:`SystemState`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from config.constants import OrderSide, OrderType
from config.logging_config import get_logger
from config.settings import TradingMode
from core.system_state import get_system_state
from market_data.alpaca_client import AlpacaClient

log = get_logger(__name__)


@dataclass
class ExecutionResult:
    accepted: bool
    mode: str
    broker_order_id: Optional[str] = None
    detail: str = ""
    payload: Dict[str, Any] = None  # type: ignore[assignment]


class AlpacaExecutor:
    def __init__(self, client: Optional[AlpacaClient] = None) -> None:
        self.client = client or AlpacaClient()
        self.state = get_system_state()

    def _build_payload(self, symbol: str, side: str, qty: float,
                       order_type: str, limit_price: Optional[float]) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "type": order_type,
            "time_in_force": "day",
        }
        if order_type in (OrderType.LIMIT.value, OrderType.STOP_LIMIT.value) and limit_price:
            payload["limit_price"] = limit_price
        return payload

    def submit(
        self, symbol: str, side: str, qty: float,
        order_type: str = OrderType.MARKET.value,
        limit_price: Optional[float] = None,
    ) -> ExecutionResult:
        mode = self.state.get_mode()
        if not self.state.is_trading_allowed():
            return ExecutionResult(False, mode.value, detail="trading_not_allowed")

        payload = self._build_payload(symbol, side, qty, order_type, limit_price)

        if mode == TradingMode.SHADOW:
            log.info("shadow_order", **payload)
            return ExecutionResult(True, mode.value, detail="shadow_logged", payload=payload)

        if mode == TradingMode.LIVE:
            if not self.client.sdk_available:
                return ExecutionResult(False, mode.value, detail="alpaca_sdk_unavailable", payload=payload)
            try:
                from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
                from alpaca.trading.enums import OrderSide as AlpSide, TimeInForce

                alp_side = AlpSide.BUY if side == OrderSide.BUY.value else AlpSide.SELL
                if order_type == OrderType.LIMIT.value and limit_price:
                    req = LimitOrderRequest(symbol=symbol, qty=qty, side=alp_side,
                                            time_in_force=TimeInForce.DAY, limit_price=limit_price)
                else:
                    req = MarketOrderRequest(symbol=symbol, qty=qty, side=alp_side,
                                             time_in_force=TimeInForce.DAY)
                order = self.client._trading.submit_order(req)  # noqa: SLF001
                oid = str(getattr(order, "id", ""))
                log.info("live_order_submitted", broker_order_id=oid, **payload)
                return ExecutionResult(True, mode.value, broker_order_id=oid,
                                       detail="submitted", payload=payload)
            except Exception as exc:  # noqa: BLE001
                log.exception("live_order_error")
                return ExecutionResult(False, mode.value, detail=f"error:{exc}", payload=payload)

        return ExecutionResult(False, mode.value, detail="mode_does_not_route_live", payload=payload)
