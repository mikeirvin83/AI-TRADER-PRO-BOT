"""Pullback-to-moving-average continuation in an established trend."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, Optional

import pandas as pd

from config.constants import MarketRegime, SignalDirection, StrategyStatus
from core.clock import utc_now
from strategies.base_strategy import BaseStrategy, StrategySignal, SignalValidationError

class TrendPullbackStrategy(BaseStrategy):
    name = "trend_pullback"
    version = "0.1.0"
    status = StrategyStatus.UNDER_RESEARCH
    category = "trend"
    allowed_regimes = [MarketRegime.STRONG_UPTREND, MarketRegime.WEAK_UPTREND]

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
        sma20 = self._last(features, 'sma_20')
        sma50 = self._last(features, 'sma_50')
        rsi = self._last(features, 'rsi_14')
        if None in (sma20, sma50, rsi):
            return None
        if not (sma20 > sma50 and close <= sma20 and rsi < 45):
            return None
        direction = SignalDirection.LONG
        entry, stop, target = close, close - 1.5*atr, close + 3*atr
        score = 75 + min(15, (45 - rsi))
        invalidation = 'Close below SMA50'
        rationale = {'sma_20': sma20, 'sma_50': sma50, 'rsi': rsi}
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
