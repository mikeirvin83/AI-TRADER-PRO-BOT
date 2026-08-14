"""Reversion to VWAP after stretched deviation."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, Optional

import pandas as pd

from config.constants import MarketRegime, SignalDirection, StrategyStatus
from core.clock import utc_now
from strategies.base_strategy import BaseStrategy, StrategySignal, SignalValidationError

class VWAPReversionStrategy(BaseStrategy):
    name = "vwap_reversion"
    version = "0.1.0"
    status = StrategyStatus.UNDER_RESEARCH
    category = "mean_reversion"
    allowed_regimes = [MarketRegime.RANGE_BOUND, MarketRegime.REVERSAL]

    def generate_signal(
        self,
        data: pd.DataFrame,
        features: pd.DataFrame,
        regime: Optional[MarketRegime] = None,
        news: Optional[Dict[str, Any]] = None,
    ) -> Optional[StrategySignal]:
        if data.empty or features.empty or not self.is_regime_allowed(regime):
            return None
        close = float(data['close'].iloc[-1])
        atr = self._last(features, 'atr_14') or (close * 0.01)
        vwap = self._last(features, 'vwap')
        if vwap is None:
            return None
        dev = (close - vwap)/atr if atr else 0
        if dev <= -2:
            direction = SignalDirection.LONG
            entry, stop, target = close, close - 1.5*atr, vwap
        elif dev >= 2:
            direction = SignalDirection.SHORT
            entry, stop, target = close, close + 1.5*atr, vwap
        else:
            return None
        score = 73.0
        invalidation = 'Deviation from VWAP keeps expanding'
        rationale = {'vwap': vwap, 'deviation_atr': dev}
        try:
            return StrategySignal(
                asset=str(data.attrs.get('symbol', 'UNKNOWN')),
                direction=direction,
                entry=entry, stop=stop, target=target,
                invalidation_condition=invalidation,
                expiration_time=utc_now() + timedelta(hours=self.params.get('ttl_hours', 24)),
                strategy_name=self.name,
                timeframe=str(data.attrs.get('timeframe', '')),
                score=float(score),
                regime=regime.value if regime else None,
                rationale=rationale,
            )
        except SignalValidationError:
            return None
