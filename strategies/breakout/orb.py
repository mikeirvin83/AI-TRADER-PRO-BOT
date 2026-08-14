"""Opening range breakout."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, Optional

import pandas as pd

from config.constants import MarketRegime, SignalDirection, StrategyStatus
from core.clock import utc_now
from strategies.base_strategy import BaseStrategy, StrategySignal, SignalValidationError

class ORBStrategy(BaseStrategy):
    name = "orb"
    version = "0.1.0"
    status = StrategyStatus.UNDER_RESEARCH
    category = "breakout"
    allowed_regimes = [MarketRegime.BREAKOUT, MarketRegime.HIGH_VOLATILITY]

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
        orb_high = self._last(features, 'orb_high')
        orb_low = self._last(features, 'orb_low')
        if None in (orb_high, orb_low):
            return None
        if close > orb_high:
            direction = SignalDirection.LONG
            entry, stop, target = close, orb_low, close + 2*(close-orb_low)
        elif close < orb_low:
            direction = SignalDirection.SHORT
            entry, stop, target = close, orb_high, close - 2*(orb_high-close)
        else:
            return None
        score = 75.0
        invalidation = 'Close back inside opening range'
        rationale = {'orb_high': orb_high, 'orb_low': orb_low}
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
