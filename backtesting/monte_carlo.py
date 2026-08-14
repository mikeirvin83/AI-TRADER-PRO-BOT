"""Monte Carlo simulator over a set of trade returns."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence

import numpy as np


@dataclass
class MonteCarloResult:
    n_simulations: int
    median_return: float
    p5_return: float
    p95_return: float
    median_max_drawdown: float
    p95_max_drawdown: float
    probability_of_ruin: float
    ending_returns: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict:
        d = self.__dict__.copy()
        # keep the raw distribution small when serialising
        d["ending_returns"] = self.ending_returns[:1000]
        return d


class MonteCarloSimulator:
    def __init__(self, n_simulations: int = 10_000, ruin_threshold: float = 0.5,
                 seed: int | None = 42) -> None:
        self.n = n_simulations
        self.ruin_threshold = ruin_threshold
        self.rng = np.random.default_rng(seed)

    def run(self, trade_returns: Sequence[float]) -> MonteCarloResult:
        """Bootstrap-resample the trade return sequence ``n`` times.

        ``trade_returns`` are per-trade fractional returns (e.g. +0.02 = +2%).
        Compounded per simulation to get an ending multiple and path drawdown.
        """
        r = np.asarray(trade_returns, dtype=float)
        if r.size == 0:
            return MonteCarloResult(self.n, 0, 0, 0, 0, 0, 0.0, [])

        k = r.size
        ending: List[float] = []
        max_dds: List[float] = []
        ruined = 0

        for _ in range(self.n):
            sample = self.rng.choice(r, size=k, replace=True)
            equity = np.cumprod(1.0 + sample)
            ending_ret = float(equity[-1] - 1.0)
            peaks = np.maximum.accumulate(equity)
            dd = float(np.max((peaks - equity) / peaks)) if peaks.size else 0.0
            ending.append(ending_ret)
            max_dds.append(dd)
            if dd >= self.ruin_threshold:
                ruined += 1

        ending_arr = np.asarray(ending)
        dd_arr = np.asarray(max_dds)
        return MonteCarloResult(
            n_simulations=self.n,
            median_return=float(np.median(ending_arr)),
            p5_return=float(np.percentile(ending_arr, 5)),
            p95_return=float(np.percentile(ending_arr, 95)),
            median_max_drawdown=float(np.median(dd_arr)),
            p95_max_drawdown=float(np.percentile(dd_arr, 95)),
            probability_of_ruin=float(ruined / self.n),
            ending_returns=ending,
        )
