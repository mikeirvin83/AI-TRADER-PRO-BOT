"""Overfitting detection heuristics."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence

import numpy as np


@dataclass
class OverfittingReport:
    is_overfit: bool
    walk_forward_efficiency: float
    param_sensitivity: float
    degradation: float
    notes: List[str]


class OverfittingDetector:
    """Flags likely-overfit strategies from validation statistics.

    Signals used:
    * Walk-forward efficiency (OOS/IS) far below 1.0 -> overfit.
    * High parameter sensitivity (std of returns across nearby params).
    * Large IS->OOS performance degradation.
    """

    def __init__(self, min_efficiency: float = 0.5, max_sensitivity: float = 0.5,
                 max_degradation: float = 0.5) -> None:
        self.min_efficiency = min_efficiency
        self.max_sensitivity = max_sensitivity
        self.max_degradation = max_degradation

    def evaluate(self, is_return: float, oos_return: float,
                 wf_efficiency: float,
                 param_grid_returns: Sequence[float] | None = None) -> OverfittingReport:
        notes: List[str] = []
        degradation = 0.0
        if is_return > 0:
            degradation = max(0.0, (is_return - oos_return) / abs(is_return))

        sensitivity = 0.0
        if param_grid_returns and len(param_grid_returns) > 1:
            arr = np.asarray(param_grid_returns, dtype=float)
            mean = np.mean(np.abs(arr)) or 1e-9
            sensitivity = float(np.std(arr) / mean)

        is_overfit = False
        if wf_efficiency < self.min_efficiency:
            is_overfit = True
            notes.append(f"low_walk_forward_efficiency:{wf_efficiency:.2f}")
        if sensitivity > self.max_sensitivity:
            is_overfit = True
            notes.append(f"high_param_sensitivity:{sensitivity:.2f}")
        if degradation > self.max_degradation:
            is_overfit = True
            notes.append(f"high_is_oos_degradation:{degradation:.2f}")

        return OverfittingReport(is_overfit, wf_efficiency, sensitivity, degradation, notes)
