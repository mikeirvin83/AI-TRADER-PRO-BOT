"""Fade volatility spikes back toward the mean."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, Optional

import pandas as pd

from config.constants import MarketRegime, SignalDirection, StrategyStatus
from core.clock import utc_now
from strategies.base_strategy import BaseStrategy, StrategySignal, SignalValidationError

class VolatilityReversionStrategy(BaseStrategy):
    name = "volatility_reversion"
    version = "0.1.0"
    status = StrategyStatus.UNDER_RESEARCH
    category = "mean_reversion"
    allowed_regimes = [MarketRegime.HIGH_VOLATILITY, MarketRegime.REVERSAL]

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
        bb_bw = self._last(features, 'bb_bandwidth')
        mid = self._last(features, 'bb_mid')
        if None in (bb_bw, mid) or bb_bw < 0.05:
            return None
        if close > mid:
            direction = SignalDirection.SHORT
            entry, stop, target = close, close + 2*atr, mid
        else:
            direction = SignalDirection.LONG
            entry, stop, target = close, close - 2*atr, mid
        score = 71.0
        invalidation = 'Volatility keeps expanding, trend forms'
        rationale = {'bb_bandwidth': bb_bw, 'bb_mid': mid}
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
