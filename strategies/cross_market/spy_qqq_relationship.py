"""SPY/QQQ relationship (cross-market) strategy.

Trades divergence between two correlated index ETFs. This strategy consumes a
secondary symbol's data via ``self.params['peer_data']`` (an OHLCV DataFrame);
if unavailable it safely returns no signal (never fabricates the peer series).
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from config.constants import MarketRegime, SignalDirection, StrategyStatus
from core.clock import utc_now
from strategies.base_strategy import BaseStrategy, SignalValidationError, StrategySignal


class SPYQQQRelationshipStrategy(BaseStrategy):
    name = "spy_qqq_relationship"
    version = "0.1.0"
    status = StrategyStatus.UNDER_RESEARCH
    category = "cross_market"
    allowed_regimes = [MarketRegime.RANGE_BOUND, MarketRegime.REVERSAL, MarketRegime.CHOPPY]

    def generate_signal(
        self,
        data: pd.DataFrame,
        features: pd.DataFrame,
        regime: Optional[MarketRegime] = None,
        news: Optional[Dict[str, Any]] = None,
    ) -> Optional[StrategySignal]:
        peer: Optional[pd.DataFrame] = self.params.get("peer_data")
        if data.empty or peer is None or peer.empty or not self.is_regime_allowed(regime):
            return None

        lookback = int(self.params.get("lookback", 50))
        a = data["close"].pct_change().dropna().tail(lookback)
        b = peer["close"].pct_change().dropna().tail(lookback)
        n = min(len(a), len(b))
        if n < 20:
            return None
        a, b = a.iloc[-n:], b.iloc[-n:]

        spread = (a.cumsum() - b.cumsum())
        z = (spread.iloc[-1] - spread.mean()) / (spread.std() or np.nan)
        if not np.isfinite(z) or abs(z) < 2.0:
            return None

        close = float(data["close"].iloc[-1])
        atr = self._last(features, "atr_14") or close * 0.01
        # Mean-revert the spread: if this asset outperformed (z>0), short it.
        if z > 0:
            direction = SignalDirection.SHORT
            entry, stop, target = close, close + 2 * atr, close - 2 * atr
        else:
            direction = SignalDirection.LONG
            entry, stop, target = close, close - 2 * atr, close + 2 * atr

        try:
            return StrategySignal(
                asset=str(data.attrs.get("symbol", "UNKNOWN")),
                direction=direction,
                entry=entry, stop=stop, target=target,
                invalidation_condition="Spread z-score fails to mean-revert",
                expiration_time=utc_now() + timedelta(hours=self.params.get("ttl_hours", 24)),
                strategy_name=self.name,
                timeframe=str(data.attrs.get("timeframe", "")),
                score=72.0 + min(18.0, (abs(z) - 2.0) * 6),
                regime=regime.value if regime else None,
                rationale={"spread_zscore": float(z), "lookback": n},
            )
        except SignalValidationError:
            return None
