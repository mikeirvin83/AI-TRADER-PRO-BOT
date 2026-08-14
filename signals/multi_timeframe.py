"""Multi-timeframe (MTF) analysis helper."""
from __future__ import annotations

from typing import Dict, Optional

import pandas as pd

from config.constants import Timeframe
from features.trend import ema


class MultiTimeframeAnalyzer:
    """Aggregates directional bias across several timeframes."""

    def __init__(self, fast: int = 9, slow: int = 21) -> None:
        self.fast = fast
        self.slow = slow

    def bias(self, close: pd.Series) -> int:
        """+1 bullish, -1 bearish, 0 neutral, from EMA relationship."""
        if close.dropna().shape[0] < self.slow:
            return 0
        f = ema(close, self.fast).iloc[-1]
        s = ema(close, self.slow).iloc[-1]
        if pd.isna(f) or pd.isna(s):
            return 0
        return 1 if f > s else (-1 if f < s else 0)

    def alignment(self, frames: Dict[Timeframe, pd.DataFrame]) -> Dict[str, float]:
        """Return per-timeframe bias plus an aggregate alignment score (0-100)."""
        biases: Dict[str, int] = {}
        for tf, df in frames.items():
            if df is None or df.empty:
                continue
            biases[tf.value] = self.bias(df["close"])
        if not biases:
            return {"alignment_score": 0.0}
        agree = abs(sum(biases.values()))
        score = 100.0 * agree / len(biases)
        result: Dict[str, float] = {f"bias_{k}": float(v) for k, v in biases.items()}
        result["alignment_score"] = round(score, 2)
        result["net_bias"] = float(sum(biases.values()))
        return result
