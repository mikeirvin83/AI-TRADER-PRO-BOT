"""Position sizing.

Every method returns an integer/rounded quantity that respects
``MAX_POSITION_SIZE_PCT`` of account equity. Futures sizing uses contract specs
(tick_size, tick_value, contract_multiplier) — NEVER the per-share stock formula.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from config.constants import FUTURES_SPECS
from config.logging_config import get_logger
from config.settings import Settings, get_settings

log = get_logger(__name__)


@dataclass
class SizingResult:
    quantity: float
    dollar_risk: float
    notional: float
    method: str
    capped: bool = False
    reason: str = ""


class PositionSizer:
    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()

    # ------------------------------------------------------------------ #
    def _cap(self, qty: float, entry: float, account_value: float, contract_multiplier: float = 1.0) -> tuple[float, bool]:
        """Clamp quantity so notional <= MAX_POSITION_SIZE_PCT of equity."""
        max_notional = account_value * self.settings.MAX_POSITION_SIZE_PCT
        per_unit_notional = entry * contract_multiplier
        if per_unit_notional <= 0:
            return 0.0, True
        max_qty = max_notional / per_unit_notional
        if qty > max_qty:
            return math.floor(max_qty), True
        return qty, False

    # ------------------------------------------------------------------ #
    def fixed_fractional(
        self, account_value: float, risk_pct: float, entry: float, stop: float
    ) -> SizingResult:
        """Risk a fixed fraction of equity; shares = risk$ / per-share risk."""
        per_share_risk = abs(entry - stop)
        if per_share_risk <= 0:
            return SizingResult(0, 0, 0, "fixed_fractional", True, "invalid_stop")
        dollar_risk = account_value * risk_pct
        qty = math.floor(dollar_risk / per_share_risk)
        qty, capped = self._cap(qty, entry, account_value)
        return SizingResult(qty, qty * per_share_risk, qty * entry, "fixed_fractional", capped)

    def atr_based(
        self, account_value: float, risk_pct: float, atr: float, entry: float,
        stop: Optional[float] = None, atr_mult: float = 2.0
    ) -> SizingResult:
        """Size using ATR as the risk unit (stop distance = atr_mult * ATR)."""
        risk_per_share = atr * atr_mult if stop is None else abs(entry - stop)
        if risk_per_share <= 0:
            return SizingResult(0, 0, 0, "atr_based", True, "invalid_atr")
        dollar_risk = account_value * risk_pct
        qty = math.floor(dollar_risk / risk_per_share)
        qty, capped = self._cap(qty, entry, account_value)
        return SizingResult(qty, qty * risk_per_share, qty * entry, "atr_based", capped)

    def volatility_adjusted(
        self, account_value: float, risk_pct: float, volatility: float, entry: float,
        stop: float
    ) -> SizingResult:
        """Scale fixed-fractional size inversely with volatility (target 20% vol)."""
        per_share_risk = abs(entry - stop)
        if per_share_risk <= 0 or volatility <= 0:
            return SizingResult(0, 0, 0, "volatility_adjusted", True, "invalid_inputs")
        target_vol = 0.20
        scale = min(1.0, target_vol / volatility)
        dollar_risk = account_value * risk_pct * scale
        qty = math.floor(dollar_risk / per_share_risk)
        qty, capped = self._cap(qty, entry, account_value)
        return SizingResult(qty, qty * per_share_risk, qty * entry, "volatility_adjusted", capped)

    # ------------------------------------------------------------------ #
    # Futures — uses contract specs, not the stock formula.
    # ------------------------------------------------------------------ #
    def futures_contracts(
        self, account_value: float, risk_pct: float, entry: float, stop: float, symbol: str
    ) -> SizingResult:
        """Number of futures contracts to risk risk_pct of equity.

        risk_per_contract = (stop distance in ticks) * tick_value.
        """
        spec = FUTURES_SPECS.get(symbol.upper())
        if spec is None:
            return SizingResult(0, 0, 0, "futures", True, f"unknown_contract:{symbol}")
        stop_distance = abs(entry - stop)
        ticks = stop_distance / spec.tick_size
        risk_per_contract = ticks * spec.tick_value
        if risk_per_contract <= 0:
            return SizingResult(0, 0, 0, "futures", True, "invalid_stop")
        dollar_risk = account_value * risk_pct
        qty = math.floor(dollar_risk / risk_per_contract)
        qty, capped = self._cap(qty, entry, account_value, spec.contract_multiplier)
        notional = qty * entry * spec.contract_multiplier
        return SizingResult(qty, qty * risk_per_contract, notional, "futures", capped)
