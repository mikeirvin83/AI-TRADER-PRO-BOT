"""Breakout confirmed by a volume surge."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, Optional

import pandas as pd

from config.constants import MarketRegime, SignalDirection, StrategyStatus
from core.clock import utc_now
from strategies.base_strategy import BaseStrategy, StrategySignal, SignalValidationError

class VolumeBreakoutStrategy(BaseStrategy):
    name = "volume_breakout"
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
        relvol = self._last(features, 'rel_volume')
        resistance = self._last(features, 'resistance')
        support = self._last(features, 'support')
        if None in (relvol, resistance, support) or relvol < 2.0:
            return None
        if close >= resistance:
            direction = SignalDirection.LONG
            entry, stop, target = close, close - 2*atr, close + 4*atr
        elif close <= support:
            direction = SignalDirection.SHORT
            entry, stop, target = close, close + 2*atr, close - 4*atr
        else:
            return None
        score = 78.0
        invalidation = 'Volume fades, breakout fails'
        rationale = {'rel_volume': relvol, 'resistance': resistance, 'support': support}
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
