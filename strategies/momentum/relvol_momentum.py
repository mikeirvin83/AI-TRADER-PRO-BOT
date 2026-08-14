"""Relative-volume driven momentum entries."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, Optional

import pandas as pd

from config.constants import MarketRegime, SignalDirection, StrategyStatus
from core.clock import utc_now
from strategies.base_strategy import BaseStrategy, StrategySignal, SignalValidationError

class RelVolMomentumStrategy(BaseStrategy):
    name = "relvol_momentum"
    version = "0.1.0"
    status = StrategyStatus.UNDER_RESEARCH
    category = "momentum"
    allowed_regimes = [MarketRegime.BREAKOUT, MarketRegime.STRONG_UPTREND, MarketRegime.HIGH_VOLATILITY]

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
        roc = self._last(features, 'roc_12')
        if None in (relvol, roc) or relvol < 1.5:
            return None
        direction = SignalDirection.LONG if roc > 0 else SignalDirection.SHORT
        if direction == SignalDirection.LONG:
            entry, stop, target = close, close - 1.5*atr, close + 3*atr
        else:
            entry, stop, target = close, close + 1.5*atr, close - 3*atr
        score = 70 + min(25, (relvol - 1.5)*10)
        invalidation = 'Relative volume normalizes below 1.0'
        rationale = {'rel_volume': relvol, 'roc': roc}
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
