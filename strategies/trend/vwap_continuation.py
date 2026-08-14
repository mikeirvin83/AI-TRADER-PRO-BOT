"""VWAP continuation: price holding above/below VWAP in trend."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, Optional

import pandas as pd

from config.constants import MarketRegime, SignalDirection, StrategyStatus
from core.clock import utc_now
from strategies.base_strategy import BaseStrategy, StrategySignal, SignalValidationError

class VWAPContinuationStrategy(BaseStrategy):
    name = "vwap_continuation"
    version = "0.1.0"
    status = StrategyStatus.UNDER_RESEARCH
    category = "trend"
    allowed_regimes = [MarketRegime.STRONG_UPTREND, MarketRegime.WEAK_UPTREND, MarketRegime.STRONG_DOWNTREND, MarketRegime.WEAK_DOWNTREND]

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
        if close > vwap:
            direction = SignalDirection.LONG
            entry, stop, target = close, vwap - 0.5*atr, close + 2.5*atr
        else:
            direction = SignalDirection.SHORT
            entry, stop, target = close, vwap + 0.5*atr, close - 2.5*atr
        score = 72 + min(18, abs(close - vwap)/atr*8)
        invalidation = 'Close crosses back through VWAP'
        rationale = {'vwap': vwap, 'close': close}
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
