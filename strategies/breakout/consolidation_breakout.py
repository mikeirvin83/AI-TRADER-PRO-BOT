"""Breakout from low-volatility consolidation (squeeze)."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, Optional

import pandas as pd

from config.constants import MarketRegime, SignalDirection, StrategyStatus
from core.clock import utc_now
from strategies.base_strategy import BaseStrategy, StrategySignal, SignalValidationError

class ConsolidationBreakoutStrategy(BaseStrategy):
    name = "consolidation_breakout"
    version = "0.1.0"
    status = StrategyStatus.UNDER_RESEARCH
    category = "breakout"
    allowed_regimes = [MarketRegime.BREAKOUT, MarketRegime.LOW_VOLATILITY]

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
        resistance = self._last(features, 'resistance')
        support = self._last(features, 'support')
        if None in (bb_bw, resistance, support) or bb_bw > 0.05:
            return None
        if close >= resistance:
            direction = SignalDirection.LONG
            entry, stop, target = close, support, close + 3*atr
        elif close <= support:
            direction = SignalDirection.SHORT
            entry, stop, target = close, resistance, close - 3*atr
        else:
            return None
        score = 76.0
        invalidation = 'Squeeze resumes, false breakout'
        rationale = {'bb_bandwidth': bb_bw, 'resistance': resistance, 'support': support}
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
