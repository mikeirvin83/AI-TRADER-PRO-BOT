"""Shadow trading engine (Phase 11).

Shadow trading is the final validation stage before *any* consideration of live
capital. A strategy that has already cleared backtest, out-of-sample,
walk-forward, Monte-Carlo and paper gates is run in SHADOW mode:

  * The decision pipeline produces real signals against real live market data.
  * Each intended order is recorded as a *shadow order* -- nothing is sent to
    any broker. No capital is ever at risk in this module.
  * The price the paper engine assumed is compared against the price that was
    actually observable/achievable in the market at fill time.
  * The resulting divergence statistics feed the SHADOW promotion gate in
    ``validation.pipeline`` (``max_divergence_pct``, default 10%).

The engine is deliberately broker-agnostic and side-effect free: callers push
observations in, and pull metrics out. This makes it trivially testable and
makes it impossible for this module to place a real order.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from config.logging_config import get_logger

log = get_logger(__name__)


class ShadowOrderStatus(str, Enum):
    """Lifecycle of a shadow order."""
    PENDING = "PENDING"        # intent recorded, awaiting market observation
    MATCHED = "MATCHED"        # observed a real achievable price
    UNFILLABLE = "UNFILLABLE"  # market never offered liquidity/price
    EXPIRED = "EXPIRED"        # observation window elapsed


@dataclass
class ShadowOrder:
    """A single intended-but-never-sent order and its market comparison."""
    order_id: str
    strategy: str
    symbol: str
    side: str
    qty: float
    intended_price: float
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: ShadowOrderStatus = ShadowOrderStatus.PENDING

    # Populated once a real market observation arrives
    observed_price: Optional[float] = None
    observed_at: Optional[datetime] = None
    observed_volume: Optional[float] = None
    reject_reason: str = ""

    @property
    def is_resolved(self) -> bool:
        return self.status is not ShadowOrderStatus.PENDING

    @property
    def price_divergence(self) -> Optional[float]:
        """Absolute fractional divergence between intended and observed price."""
        if self.observed_price is None or self.intended_price == 0:
            return None
        return abs(self.observed_price - self.intended_price) / abs(self.intended_price)

    @property
    def signed_slippage(self) -> Optional[float]:
        """Adverse (positive) or favourable (negative) slippage in price units.

        For a BUY, paying more than intended is adverse. For a SELL, receiving
        less than intended is adverse.
        """
        if self.observed_price is None:
            return None
        delta = self.observed_price - self.intended_price
        return delta if self.side.upper() == "BUY" else -delta

    @property
    def latency_seconds(self) -> Optional[float]:
        if self.observed_at is None:
            return None
        return max(0.0, (self.observed_at - self.created_at).total_seconds())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "strategy": self.strategy,
            "symbol": self.symbol,
            "side": self.side,
            "qty": self.qty,
            "intended_price": self.intended_price,
            "observed_price": self.observed_price,
            "status": self.status.value,
            "price_divergence": self.price_divergence,
            "signed_slippage": self.signed_slippage,
            "latency_seconds": self.latency_seconds,
            "reject_reason": self.reject_reason,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class DivergenceReport:
    """Aggregate divergence statistics for the SHADOW promotion gate."""
    strategy: str
    total_orders: int = 0
    matched_orders: int = 0
    unfillable_orders: int = 0
    expired_orders: int = 0
    fill_rate: float = 0.0
    mean_divergence_pct: float = 0.0
    median_divergence_pct: float = 0.0
    p95_divergence_pct: float = 0.0
    worst_divergence_pct: float = 0.0
    mean_adverse_slippage_bps: float = 0.0
    mean_latency_seconds: float = 0.0
    paper_pnl: float = 0.0
    shadow_pnl: float = 0.0
    pnl_divergence_pct: float = 0.0
    duration_days: float = 0.0
    notes: List[str] = field(default_factory=list)

    @property
    def divergence_pct(self) -> float:
        """Headline number consumed by ``ValidationPipeline.run_shadow_gate``.

        We take the *worst* of price divergence and realised P&L divergence so
        the gate cannot be gamed by a strategy whose per-order prices look tight
        but whose aggregate economics still diverge.
        """
        return max(self.mean_divergence_pct, self.pnl_divergence_pct)

    def to_metrics(self) -> Dict[str, Any]:
        """Shape expected by the SHADOW gate."""
        return {
            "divergence_pct": self.divergence_pct,
            "total_orders": self.total_orders,
            "matched_orders": self.matched_orders,
            "fill_rate": self.fill_rate,
            "mean_divergence_pct": self.mean_divergence_pct,
            "median_divergence_pct": self.median_divergence_pct,
            "p95_divergence_pct": self.p95_divergence_pct,
            "worst_divergence_pct": self.worst_divergence_pct,
            "mean_adverse_slippage_bps": self.mean_adverse_slippage_bps,
            "mean_latency_seconds": self.mean_latency_seconds,
            "paper_pnl": self.paper_pnl,
            "shadow_pnl": self.shadow_pnl,
            "pnl_divergence_pct": self.pnl_divergence_pct,
            "duration_days": self.duration_days,
            "notes": list(self.notes),
        }


class ShadowEngine:
    """Records intended orders and compares them against real market prices.

    This class NEVER communicates with a broker. It has no execution client and
    no network dependency by construction -- the only way a price enters the
    engine is via :meth:`observe_market`, which the caller supplies from the
    market-data layer.
    """

    #: Orders older than this without an observation are marked EXPIRED.
    DEFAULT_OBSERVATION_WINDOW_SECONDS = 300.0

    def __init__(
        self,
        strategy: str = "shadow",
        observation_window_seconds: float = DEFAULT_OBSERVATION_WINDOW_SECONDS,
        min_fill_rate: float = 0.90,
    ) -> None:
        self.strategy = strategy
        self.observation_window_seconds = observation_window_seconds
        self.min_fill_rate = min_fill_rate
        self.orders: List[ShadowOrder] = []
        self._by_id: Dict[str, ShadowOrder] = {}
        self._seq = 0
        self.started_at = datetime.now(timezone.utc)
        # Realised P&L accumulators, keyed by book.
        self._paper_pnl = 0.0
        self._shadow_pnl = 0.0

    # ------------------------------------------------------------------ #
    # Order intent recording
    # ------------------------------------------------------------------ #
    def record_intent(
        self,
        symbol: str,
        side: str,
        qty: float,
        intended_price: float,
        strategy: Optional[str] = None,
        created_at: Optional[datetime] = None,
    ) -> ShadowOrder:
        """Record an order the system *would* have sent. Nothing is transmitted."""
        self._seq += 1
        order = ShadowOrder(
            order_id=f"shadow-{self._seq:06d}",
            strategy=strategy or self.strategy,
            symbol=symbol,
            side=side.upper(),
            qty=qty,
            intended_price=intended_price,
            created_at=created_at or datetime.now(timezone.utc),
        )
        self.orders.append(order)
        self._by_id[order.order_id] = order
        log.info("shadow_intent", order_id=order.order_id, symbol=symbol,
                 side=order.side, qty=qty, price=intended_price)
        return order

    def get(self, order_id: str) -> Optional[ShadowOrder]:
        return self._by_id.get(order_id)

    def pending(self) -> List[ShadowOrder]:
        return [o for o in self.orders if o.status is ShadowOrderStatus.PENDING]

    # ------------------------------------------------------------------ #
    # Market observation
    # ------------------------------------------------------------------ #
    def observe_market(
        self,
        order_id: str,
        observed_price: Optional[float],
        observed_at: Optional[datetime] = None,
        observed_volume: Optional[float] = None,
        reject_reason: str = "",
    ) -> ShadowOrder:
        """Attach the real achievable market price to a shadow order.

        Pass ``observed_price=None`` when the market offered no liquidity at all
        -- the order is then marked UNFILLABLE, which drags down the fill rate.
        """
        order = self._by_id.get(order_id)
        if order is None:
            raise KeyError(f"unknown shadow order: {order_id}")
        if order.is_resolved:
            log.warning("shadow_already_resolved", order_id=order_id,
                        status=order.status.value)
            return order

        order.observed_at = observed_at or datetime.now(timezone.utc)
        order.observed_volume = observed_volume

        if observed_price is None or observed_price <= 0:
            order.status = ShadowOrderStatus.UNFILLABLE
            order.reject_reason = reject_reason or "no_liquidity"
            log.info("shadow_unfillable", order_id=order_id, reason=order.reject_reason)
            return order

        order.observed_price = observed_price
        order.status = ShadowOrderStatus.MATCHED
        log.info("shadow_matched", order_id=order_id,
                 intended=order.intended_price, observed=observed_price,
                 divergence=round(order.price_divergence or 0.0, 5))
        return order

    def expire_stale(self, now: Optional[datetime] = None) -> int:
        """Mark pending orders older than the observation window as EXPIRED."""
        now = now or datetime.now(timezone.utc)
        expired = 0
        for order in self.orders:
            if order.status is not ShadowOrderStatus.PENDING:
                continue
            age = (now - order.created_at).total_seconds()
            if age > self.observation_window_seconds:
                order.status = ShadowOrderStatus.EXPIRED
                order.reject_reason = "observation_window_elapsed"
                expired += 1
        if expired:
            log.info("shadow_expired", count=expired)
        return expired

    # ------------------------------------------------------------------ #
    # P&L comparison
    # ------------------------------------------------------------------ #
    def record_pnl(self, paper_pnl: float, shadow_pnl: float) -> None:
        """Accumulate realised P&L from the paper book vs the shadow book."""
        self._paper_pnl += paper_pnl
        self._shadow_pnl += shadow_pnl

    # ------------------------------------------------------------------ #
    # Reporting
    # ------------------------------------------------------------------ #
    def report(self, now: Optional[datetime] = None) -> DivergenceReport:
        """Compute aggregate divergence statistics."""
        now = now or datetime.now(timezone.utc)
        rep = DivergenceReport(strategy=self.strategy)
        rep.total_orders = len(self.orders)
        rep.duration_days = max(0.0, (now - self.started_at).total_seconds() / 86_400.0)

        matched = [o for o in self.orders if o.status is ShadowOrderStatus.MATCHED]
        rep.matched_orders = len(matched)
        rep.unfillable_orders = sum(
            1 for o in self.orders if o.status is ShadowOrderStatus.UNFILLABLE)
        rep.expired_orders = sum(
            1 for o in self.orders if o.status is ShadowOrderStatus.EXPIRED)

        resolved = rep.matched_orders + rep.unfillable_orders + rep.expired_orders
        rep.fill_rate = (rep.matched_orders / resolved) if resolved else 0.0

        if not matched:
            rep.notes.append("no_matched_orders")
            # No evidence at all -> treat as maximally divergent so the gate fails
            # closed rather than open.
            rep.mean_divergence_pct = 1.0
            rep.median_divergence_pct = 1.0
            rep.p95_divergence_pct = 1.0
            rep.worst_divergence_pct = 1.0
            return rep

        divs = sorted(o.price_divergence or 0.0 for o in matched)
        rep.mean_divergence_pct = sum(divs) / len(divs)
        rep.median_divergence_pct = statistics.median(divs)
        rep.p95_divergence_pct = divs[min(len(divs) - 1, int(0.95 * len(divs)))]
        rep.worst_divergence_pct = divs[-1]

        adverse_bps = []
        for o in matched:
            slip = o.signed_slippage
            if slip is not None and o.intended_price:
                adverse_bps.append(slip / abs(o.intended_price) * 10_000.0)
        rep.mean_adverse_slippage_bps = (
            sum(adverse_bps) / len(adverse_bps) if adverse_bps else 0.0)

        lats = [o.latency_seconds for o in matched if o.latency_seconds is not None]
        rep.mean_latency_seconds = sum(lats) / len(lats) if lats else 0.0

        rep.paper_pnl = self._paper_pnl
        rep.shadow_pnl = self._shadow_pnl
        if self._paper_pnl:
            rep.pnl_divergence_pct = (
                abs(self._shadow_pnl - self._paper_pnl) / abs(self._paper_pnl))
        elif self._shadow_pnl:
            rep.pnl_divergence_pct = 1.0

        if rep.fill_rate < self.min_fill_rate:
            rep.notes.append(
                f"fill_rate={rep.fill_rate:.2f}<min={self.min_fill_rate:.2f}")
        if rep.mean_adverse_slippage_bps > 0:
            rep.notes.append(
                f"adverse_slippage={rep.mean_adverse_slippage_bps:.1f}bps")
        return rep

    # ------------------------------------------------------------------ #
    def gate_metrics(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        """Metrics dict ready to hand to ``ValidationPipeline.run_shadow_gate``."""
        return self.report(now).to_metrics()

    def status(self) -> Dict[str, Any]:
        return {
            "strategy": self.strategy,
            "total_orders": len(self.orders),
            "pending": len(self.pending()),
            "started_at": self.started_at.isoformat(),
            "broker_connected": False,  # structurally impossible in this module
        }
