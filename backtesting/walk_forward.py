"""Walk-forward tester — rolling in-sample/out-of-sample evaluation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from config.logging_config import get_logger
from backtesting.backtest_engine import BacktestConfig, BacktestEngine
from strategies.base_strategy import BaseStrategy

log = get_logger(__name__)


@dataclass
class WalkForwardResult:
    windows: List[Dict[str, Any]] = field(default_factory=list)
    aggregate: Dict[str, float] = field(default_factory=dict)
    efficiency: float = 0.0  # mean OOS return / mean IS return


class WalkForwardTester:
    def __init__(self, n_windows: int = 5, oos_fraction: float = 0.3,
                 config: Optional[BacktestConfig] = None) -> None:
        self.n_windows = n_windows
        self.oos_fraction = oos_fraction
        self.config = config or BacktestConfig()

    def run(self, strategy: BaseStrategy, data: pd.DataFrame,
            symbol: str = "TEST") -> WalkForwardResult:
        n = len(data)
        if n < self.n_windows * 100:
            log.warning("walk_forward_limited_data", rows=n)
        window_size = n // self.n_windows
        engine = BacktestEngine(self.config)
        windows: List[Dict[str, Any]] = []
        is_returns: List[float] = []
        oos_returns: List[float] = []

        for w in range(self.n_windows):
            start = w * window_size
            end = min(start + window_size, n)
            if end - start < 60:
                continue
            split = start + int((end - start) * (1 - self.oos_fraction))
            is_data = data.iloc[start:split]
            oos_data = data.iloc[split:end]
            if len(is_data) < 55 or len(oos_data) < 10:
                continue
            is_res = engine.run(strategy, is_data, symbol)
            oos_res = engine.run(strategy, oos_data, symbol)
            is_returns.append(is_res.metrics.total_return)
            oos_returns.append(oos_res.metrics.total_return)
            windows.append({
                "window": w,
                "is_return": is_res.metrics.total_return,
                "oos_return": oos_res.metrics.total_return,
                "oos_sharpe": oos_res.metrics.sharpe,
                "oos_max_dd": oos_res.metrics.max_drawdown,
            })

        mean_is = float(np.mean(is_returns)) if is_returns else 0.0
        mean_oos = float(np.mean(oos_returns)) if oos_returns else 0.0
        efficiency = float(mean_oos / mean_is) if mean_is not in (0.0,) else 0.0
        aggregate = {"mean_is_return": mean_is, "mean_oos_return": mean_oos,
                     "n_windows": len(windows)}
        return WalkForwardResult(windows, aggregate, efficiency)
