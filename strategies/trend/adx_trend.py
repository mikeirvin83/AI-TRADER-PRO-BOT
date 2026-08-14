"""ADX-confirmed trend entries (strong directional movement)."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, Optional

import pandas as pd

from config.constants import MarketRegime, SignalDirection, StrategyStatus
from core.clock import utc_now
from strategies.base_strategy import BaseStrategy, StrategySignal, SignalValidationError

class ADXTrendStrategy(BaseStrategy):
    name = "adx_trend"
    version = "0.1.0"
    status = StrategyStatus.UNDER_RESEARCH
    category = "trend"
    allowed_regimes = [MarketRegime.STRONG_UPTREND, MarketRegime.STRONG_DOWNTREND]

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
        adx = self._last(features, 'adx')
        plus_di = self._last(features, 'plus_di')
        minus_di = self._last(features, 'minus_di')
        if None in (adx, plus_di, minus_di) or adx < 25:
            return None
        if plus_di > minus_di:
            direction = SignalDirection.LONG
            entry, stop, target = close, close - 2*atr, close + 4*atr
        else:
            direction = SignalDirection.SHORT
            entry, stop, target = close, close + 2*atr, close - 4*atr
        score = 70 + min(25, (adx - 25))
        invalidation = 'ADX falls below 20'
        rationale = {'adx': adx, 'plus_di': plus_di, 'minus_di': minus_di}
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
