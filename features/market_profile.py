"""Market profile — Point of Control (POC), Value Area High/Low, volume profile."""
from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd


def volume_profile(df: pd.DataFrame, bins: int = 30) -> pd.DataFrame:
    """Bucket traded volume by price level using typical price."""
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    lo, hi = typical.min(), typical.max()
    if not np.isfinite(lo) or not np.isfinite(hi) or lo == hi:
        return pd.DataFrame(columns=["price_low", "price_high", "volume"])
    edges = np.linspace(lo, hi, bins + 1)
    idx = np.clip(np.digitize(typical, edges) - 1, 0, bins - 1)
    vol = np.zeros(bins)
    for i, v in zip(idx, df["volume"].to_numpy()):
        vol[i] += v
    return pd.DataFrame(
        {"price_low": edges[:-1], "price_high": edges[1:], "volume": vol}
    )


def profile_levels(df: pd.DataFrame, bins: int = 30, value_area_pct: float = 0.70) -> Dict[str, float]:
    """Compute POC, VAH, VAL for the given frame."""
    prof = volume_profile(df, bins)
    if prof.empty or prof["volume"].sum() == 0:
        return {"poc": float("nan"), "vah": float("nan"), "val": float("nan")}
    prof = prof.copy()
    prof["mid"] = (prof["price_low"] + prof["price_high"]) / 2.0
    poc_row = prof.loc[prof["volume"].idxmax()]
    poc = float(poc_row["mid"])

    total = prof["volume"].sum()
    target = total * value_area_pct
    order = prof.sort_values("volume", ascending=False)
    cum, selected = 0.0, []
    for _, row in order.iterrows():
        selected.append(row["mid"])
        cum += row["volume"]
        if cum >= target:
            break
    vah, val = max(selected), min(selected)
    return {"poc": poc, "vah": float(vah), "val": float(val)}
