"""Paper trading simulator.

Maintains simulated cash, positions and P&L. Fills orders at the NEXT bar's open
(no look-ahead) with a configurable slippage model. Tracks realised/unrealised
P&L and drawdown in real time.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional

from config.constants import OrderSide
from config.logging_config import get_logger

log = get_logger(__name__)

SlippageModel = Literal["none", "fixed_bps", "volume_based"]


@dataclass
class PaperPosition:
    symbol: str
    qty: float = 0.0
    avg_price: float = 0.0
    realized_pnl: float = 0.0

    def market_value(self, price: float) -> float:
        return self.qty * price

    def unrealized(self, price: float) -> float:
        return (price - self.avg_price) * self.qty


@dataclass
class PaperFill:
    symbol: str
    side: str
    qty: float
    price: float
    slippage: float
    commission: float
    filled_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class PaperEngine:
    def __init__(
        self,
        starting_cash: float = 100_000.0,
        slippage_model: SlippageModel = "fixed_bps",
        slippage_bps: float = 1.0,
        commission_per_share: float = 0.0,
    ) -> None:
        self.cash = starting_cash
        self.starting_cash = starting_cash
        self.slippage_model = slippage_model
        self.slippage_bps = slippage_bps
        self.commission_per_share = commission_per_share
        self.positions: Dict[str, PaperPosition] = {}
        self.fills: List[PaperFill] = []
        self.peak_equity = starting_cash

    # ------------------------------------------------------------------ #
    def _apply_slippage(self, price: float, side: str, volume: Optional[float] = None) -> float:
        if self.slippage_model == "none":
            return price
        if self.slippage_model == "fixed_bps":
            adj = price * (self.slippage_bps / 10_000.0)
        else:  # volume_based — larger impact when volume small (bounded)
            base = self.slippage_bps / 10_000.0
            factor = 1.0 if not volume else min(3.0, 10_000.0 / max(volume, 1.0))
            adj = price * base * factor
        return price + adj if side == OrderSide.BUY.value else price - adj

    def fill_order(
        self, symbol: str, side: str, qty: float, fill_price: float,
        volume: Optional[float] = None,
    ) -> PaperFill:
        """Execute a fill at the provided price (typically next bar open)."""
        exec_price = self._apply_slippage(fill_price, side, volume)
        slippage = abs(exec_price - fill_price) * qty
        commission = self.commission_per_share * qty

        pos = self.positions.setdefault(symbol, PaperPosition(symbol))
        signed = qty if side == OrderSide.BUY.value else -qty

        if pos.qty == 0 or (pos.qty > 0) == (signed > 0):
            # opening or adding — weighted average price
            new_qty = pos.qty + signed
            if new_qty != 0:
                pos.avg_price = (pos.avg_price * pos.qty + exec_price * signed) / new_qty
            pos.qty = new_qty
        else:
            # reducing / closing — realise P&L
            closing = min(abs(signed), abs(pos.qty))
            direction = 1 if pos.qty > 0 else -1
            pos.realized_pnl += (exec_price - pos.avg_price) * closing * direction
            pos.qty += signed
            if pos.qty == 0:
                pos.avg_price = 0.0

        self.cash -= signed * exec_price + commission
        fill = PaperFill(symbol, side, qty, exec_price, slippage, commission)
        self.fills.append(fill)
        log.info("paper_fill", symbol=symbol, side=side, qty=qty, price=round(exec_price, 4))
        return fill

    # ------------------------------------------------------------------ #
    def portfolio_value(self, marks: Dict[str, float]) -> float:
        equity = self.cash
        for sym, pos in self.positions.items():
            price = marks.get(sym, pos.avg_price)
            equity += pos.market_value(price)
        self.peak_equity = max(self.peak_equity, equity)
        return equity

    def drawdown(self, marks: Dict[str, float]) -> float:
        equity = self.portfolio_value(marks)
        if self.peak_equity <= 0:
            return 0.0
        return max(0.0, (self.peak_equity - equity) / self.peak_equity)

    def snapshot(self, marks: Dict[str, float]) -> dict:
        return {
            "cash": round(self.cash, 2),
            "equity": round(self.portfolio_value(marks), 2),
            "drawdown_pct": round(self.drawdown(marks), 4),
            "open_positions": sum(1 for p in self.positions.values() if p.qty != 0),
            "realized_pnl": round(sum(p.realized_pnl for p in self.positions.values()), 2),
        }
