"""Shadow trading loop (Phase 11).

Runs a strategy's decision pipeline against live market data while recording
intended orders in a :class:`~execution.shadow_engine.ShadowEngine` instead of
sending them anywhere. Every intent is later reconciled against the price that
was actually observable in the market, producing the divergence statistics that
the SHADOW promotion gate consumes.

Safety properties (enforced, not advisory):
  * Refuses to start unless ``TRADING_MODE`` is PAPER, SHADOW or RESEARCH.
  * Holds no execution client -- there is no code path to a broker.
  * Aborts every tick if the system is emergency-stopped.
  * Never promotes a strategy; it only produces evidence for the pipeline.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import pandas as pd

from config.constants import DEFAULT_EQUITY_UNIVERSE, OrderSide, Timeframe
from config.logging_config import get_logger
from config.settings import TradingMode, get_settings
from core.system_state import get_system_state
from execution.paper_engine import PaperEngine
from execution.shadow_engine import (
    DivergenceReport,
    ShadowEngine,
    ShadowOrder,
    ShadowOrderStatus,
)
from orchestration.session_manager import SessionManager, SessionPhase

log = get_logger(__name__)

_ALLOWED_MODES = {TradingMode.PAPER, TradingMode.SHADOW, TradingMode.RESEARCH}


class ShadowTradingLoop:
    """Coordinates shadow order recording and market reconciliation.

    The loop is intentionally thin: signal generation is delegated to whatever
    callable the caller supplies (usually a bound method of the live decision
    loop), and market prices come from a supplied fetch callable. This keeps the
    loop testable without any network access.
    """

    def __init__(
        self,
        strategy_name: str,
        symbols: Optional[List[str]] = None,
        scan_interval_seconds: int = 60,
        reconcile_delay_seconds: float = 60.0,
        starting_cash: float = 100_000.0,
        signal_fn: Optional[Any] = None,
        price_fn: Optional[Any] = None,
        session_manager: Optional[SessionManager] = None,
    ) -> None:
        self.strategy_name = strategy_name
        self.symbols = symbols or list(DEFAULT_EQUITY_UNIVERSE)
        self.scan_interval = scan_interval_seconds
        self.reconcile_delay_seconds = reconcile_delay_seconds
        self.signal_fn = signal_fn
        self.price_fn = price_fn

        self.settings = get_settings()
        self.state = get_system_state()
        self.session = session_manager or SessionManager()
        self.shadow = ShadowEngine(strategy=strategy_name)
        # A parallel paper book so paper-vs-shadow P&L can be compared directly.
        self.paper = PaperEngine(starting_cash=starting_cash)

        self._running = False
        self._ticks = 0
        self._errors = 0

    # ------------------------------------------------------------------ #
    # Guards
    # ------------------------------------------------------------------ #
    def _mode_allows_shadow(self) -> bool:
        mode = getattr(self.settings, "TRADING_MODE", TradingMode.PAPER)
        try:
            mode = TradingMode(mode)
        except (ValueError, TypeError):
            return False
        return mode in _ALLOWED_MODES

    # ------------------------------------------------------------------ #
    # Recording
    # ------------------------------------------------------------------ #
    def record_signal(
        self,
        symbol: str,
        side: str,
        qty: float,
        intended_price: float,
        created_at: Optional[datetime] = None,
    ) -> ShadowOrder:
        """Record a shadow intent and mirror it into the paper book."""
        order = self.shadow.record_intent(
            symbol=symbol,
            side=side,
            qty=qty,
            intended_price=intended_price,
            strategy=self.strategy_name,
            created_at=created_at,
        )
        # Mirror into the paper book at the intended price so that the two books
        # differ only by real-world execution effects.
        paper_side = (OrderSide.BUY.value if side.upper() == "BUY"
                      else OrderSide.SELL.value)
        self.paper.fill_order(symbol, paper_side, qty, intended_price)
        return order

    def reconcile(
        self,
        prices: Dict[str, Optional[float]],
        now: Optional[datetime] = None,
    ) -> int:
        """Attach observed market prices to all pending shadow orders.

        ``prices`` maps symbol -> achievable price, or ``None`` when the market
        offered no liquidity. Returns the number of orders resolved.
        """
        now = now or datetime.now(timezone.utc)
        resolved = 0
        for order in list(self.shadow.pending()):
            age = (now - order.created_at).total_seconds()
            if age < self.reconcile_delay_seconds:
                continue
            if order.symbol not in prices:
                continue
            observed = prices[order.symbol]
            self.shadow.observe_market(
                order.order_id, observed, observed_at=now)
            if observed is not None and observed > 0:
                # Realised difference between the two books for this order.
                signed = 1.0 if order.side.upper() == "BUY" else -1.0
                paper_leg = -signed * order.intended_price * order.qty
                shadow_leg = -signed * observed * order.qty
                self.shadow.record_pnl(paper_leg, shadow_leg)
            resolved += 1
        self.shadow.expire_stale(now)
        return resolved

    # ------------------------------------------------------------------ #
    # Async loop
    # ------------------------------------------------------------------ #
    async def _tick(self) -> None:
        self._ticks += 1

        if self.state.is_emergency_stopped():
            log.warning("shadow_tick_skipped_emergency_stop")
            return

        if self.session.current_phase() is not SessionPhase.REGULAR:
            return

        # 1. Generate intents (delegated).
        if self.signal_fn is not None:
            intents = self.signal_fn()
            if asyncio.iscoroutine(intents):
                intents = await intents
            for intent in intents or []:
                self.record_signal(
                    symbol=intent["symbol"],
                    side=intent["side"],
                    qty=float(intent["qty"]),
                    intended_price=float(intent["price"]),
                )

        # 2. Reconcile pending intents against real prices.
        if self.price_fn is not None:
            pending_symbols = sorted({o.symbol for o in self.shadow.pending()})
            if pending_symbols:
                prices = self.price_fn(pending_symbols)
                if asyncio.iscoroutine(prices):
                    prices = await prices
                if prices:
                    self.reconcile(prices)

    async def run(self) -> None:
        """Run the shadow loop until :meth:`stop` is called."""
        if not self._mode_allows_shadow():
            raise RuntimeError(
                "ShadowTradingLoop refuses to start: TRADING_MODE must be "
                "PAPER, SHADOW or RESEARCH."
            )
        self._running = True
        log.info("shadow_loop_started", strategy=self.strategy_name,
                 symbols=len(self.symbols))
        try:
            while self._running:
                try:
                    await self._tick()
                except Exception as exc:  # pragma: no cover - defensive
                    self._errors += 1
                    log.error("shadow_tick_error", error=str(exc))
                await asyncio.sleep(self.scan_interval)
        finally:
            log.info("shadow_loop_stopped", strategy=self.strategy_name,
                     ticks=self._ticks, errors=self._errors)

    def stop(self) -> None:
        self._running = False

    # ------------------------------------------------------------------ #
    # Reporting
    # ------------------------------------------------------------------ #
    def divergence_report(self, now: Optional[datetime] = None) -> DivergenceReport:
        return self.shadow.report(now)

    def gate_metrics(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        return self.shadow.gate_metrics(now)

    def submit_to_pipeline(self, pipeline: Any, state: Any, now: Optional[datetime] = None):
        """Hand the accumulated divergence evidence to the SHADOW gate.

        This only *evaluates* the gate. Passing the SHADOW gate advances the
        strategy to RISK_REVIEW -- it never enables live trading.
        """
        return pipeline.run_shadow_gate(state, self.gate_metrics(now))

    def status(self) -> Dict[str, Any]:
        rep = self.shadow.report()
        return {
            "strategy": self.strategy_name,
            "running": self._running,
            "ticks": self._ticks,
            "errors": self._errors,
            "symbols": len(self.symbols),
            "session_phase": self.session.current_phase().value,
            "orders": rep.total_orders,
            "matched": rep.matched_orders,
            "fill_rate": round(rep.fill_rate, 4),
            "divergence_pct": round(rep.divergence_pct, 5),
            "live_trading": False,
        }
