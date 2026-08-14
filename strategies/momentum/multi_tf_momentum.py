"""Multi-timeframe momentum alignment (placeholder single-TF proxy using RSI+ROC)."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, Optional

import pandas as pd

from config.constants import MarketRegime, SignalDirection, StrategyStatus
from core.clock import utc_now
from strategies.base_strategy import BaseStrategy, StrategySignal, SignalValidationError

class MultiTFMomentumStrategy(BaseStrategy):
    name = "multi_tf_momentum"
    version = "0.1.0"
    status = StrategyStatus.UNDER_RESEARCH
    category = "momentum"
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
        rsi = self._last(features, 'rsi_14')
        roc = self._last(features, 'roc_12')
        if None in (rsi, roc):
            return None
        if rsi > 55 and roc > 0:
            direction = SignalDirection.LONG
            entry, stop, target = close, close - 2*atr, close + 3*atr
        elif rsi < 45 and roc < 0:
            direction = SignalDirection.SHORT
            entry, stop, target = close, close + 2*atr, close - 3*atr
        else:
            return None
        score = 72.0
        invalidation = 'Momentum alignment breaks across timeframes'
        rationale = {'rsi': rsi, 'roc': roc}
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
