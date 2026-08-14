"""Signal generator — runs all registered strategies over an asset's data."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from config.constants import MarketRegime
from config.logging_config import get_logger
from signals.signal_scorer import SignalScorer, SignalQuality
from strategies.base_strategy import BaseStrategy, StrategySignal

log = get_logger(__name__)


class SignalGenerator:
    def __init__(self, strategies: Optional[List[BaseStrategy]] = None,
                 scorer: Optional[SignalScorer] = None) -> None:
        self.strategies: List[BaseStrategy] = strategies or []
        self.scorer = scorer or SignalScorer()

    def register(self, strategy: BaseStrategy) -> None:
        self.strategies.append(strategy)

    def generate(
        self,
        data: pd.DataFrame,
        features: pd.DataFrame,
        regime: Optional[MarketRegime] = None,
        news: Optional[Dict[str, Any]] = None,
    ) -> List[StrategySignal]:
        """Run every strategy; return only signals meeting the qualification bar."""
        out: List[StrategySignal] = []
        for strat in self.strategies:
            try:
                sig = strat.generate_signal(data, features, regime, news)
            except Exception:  # noqa: BLE001
                log.exception("strategy_error", strategy=strat.name)
                continue
            if sig is None:
                continue
            if self.scorer.classify(sig.score) == SignalQuality.REJECTED:
                log.debug("signal_below_threshold", strategy=strat.name, score=sig.score)
                continue
            out.append(sig)
        log.info("signals_generated", count=len(out), n_strategies=len(self.strategies))
        return out
