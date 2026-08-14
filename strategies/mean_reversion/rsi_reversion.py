"""RSI oversold/overbought mean reversion."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, Optional

import pandas as pd

from config.constants import MarketRegime, SignalDirection, StrategyStatus
from core.clock import utc_now
from strategies.base_strategy import BaseStrategy, StrategySignal, SignalValidationError

class RSIReversionStrategy(BaseStrategy):
    name = "rsi_reversion"
    version = "0.1.0"
    status = StrategyStatus.UNDER_RESEARCH
    category = "mean_reversion"
    allowed_regimes = [MarketRegime.RANGE_BOUND, MarketRegime.REVERSAL, MarketRegime.LOW_VOLATILITY]

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
        if rsi is None:
            return None
        if rsi <= 30:
            direction = SignalDirection.LONG
            entry, stop, target = close, close - 1.5*atr, close + 2*atr
        elif rsi >= 70:
            direction = SignalDirection.SHORT
            entry, stop, target = close, close + 1.5*atr, close - 2*atr
        else:
            return None
        score = 72 + min(18, abs(50 - rsi) - 20)
        invalidation = 'RSI fails to revert toward 50'
        rationale = {'rsi': rsi}
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
