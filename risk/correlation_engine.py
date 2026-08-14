"""Correlation monitoring across the active portfolio."""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from config.logging_config import get_logger

log = get_logger(__name__)


class CorrelationEngine:
    def __init__(self, high_corr_threshold: float = 0.7) -> None:
        self.high_corr_threshold = high_corr_threshold

    def correlation_matrix(self, returns: pd.DataFrame) -> pd.DataFrame:
        """Pearson correlation of per-symbol return series."""
        if returns.empty:
            return pd.DataFrame()
        return returns.corr()

    def correlated_clusters(self, returns: pd.DataFrame) -> List[List[str]]:
        """Group symbols whose pairwise correlation exceeds the threshold."""
        corr = self.correlation_matrix(returns)
        if corr.empty:
            return []
        symbols = list(corr.columns)
        visited: set[str] = set()
        clusters: List[List[str]] = []
        for s in symbols:
            if s in visited:
                continue
            cluster = [s]
            visited.add(s)
            for other in symbols:
                if other in visited:
                    continue
                if abs(corr.loc[s, other]) >= self.high_corr_threshold:
                    cluster.append(other)
                    visited.add(other)
            clusters.append(cluster)
        return clusters

    def max_pairwise_correlation(self, returns: pd.DataFrame, symbol: str) -> float:
        corr = self.correlation_matrix(returns)
        if corr.empty or symbol not in corr.columns:
            return 0.0
        row = corr[symbol].drop(labels=[symbol], errors="ignore")
        return float(row.abs().max()) if not row.empty else 0.0
