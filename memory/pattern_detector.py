"""Statistical pattern detector for trade history.

Identifies recurring patterns (time-of-day, day-of-week, regime-dependent,
streak-based) from completed trade data. Works entirely from statistics —
no LLM required. Results feed into the learning engine and knowledge store.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np

from config.logging_config import get_logger

log = get_logger(__name__)


class PatternDetector:
    """Detect recurring patterns in trade outcomes."""

    def analyze(
        self,
        trades: List[Dict[str, Any]],
        min_sample: int = 10,
    ) -> Dict[str, Any]:
        """Run all pattern detectors and return consolidated results."""
        if len(trades) < min_sample:
            return {"status": "insufficient_data", "n_trades": len(trades)}

        return {
            "n_trades": len(trades),
            "time_patterns": self._time_of_day_patterns(trades, min_sample),
            "day_patterns": self._day_of_week_patterns(trades, min_sample),
            "regime_patterns": self._regime_patterns(trades, min_sample),
            "streak_patterns": self._streak_analysis(trades),
            "exit_patterns": self._exit_reason_patterns(trades, min_sample),
            "r_multiple_distribution": self._r_multiple_analysis(trades),
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }

    def _time_of_day_patterns(
        self, trades: List[Dict[str, Any]], min_sample: int,
    ) -> Dict[str, Any]:
        """Analyse P&L by hour of entry."""
        by_hour: Dict[int, List[float]] = defaultdict(list)
        for t in trades:
            entry = t.get("entry_time")
            pnl = t.get("pnl", 0) or 0
            if isinstance(entry, str):
                try:
                    entry = datetime.fromisoformat(entry)
                except (ValueError, TypeError):
                    continue
            if isinstance(entry, datetime):
                by_hour[entry.hour].append(pnl)

        results: Dict[str, Any] = {}
        for hour, pnls in sorted(by_hour.items()):
            if len(pnls) >= min_sample:
                arr = np.array(pnls)
                results[str(hour)] = {
                    "n": len(pnls),
                    "avg_pnl": round(float(arr.mean()), 2),
                    "win_rate": round(float(np.sum(arr > 0) / len(arr)), 3),
                    "total": round(float(arr.sum()), 2),
                }
        return results

    def _day_of_week_patterns(
        self, trades: List[Dict[str, Any]], min_sample: int,
    ) -> Dict[str, Any]:
        """Analyse P&L by day of week."""
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
                     "Saturday", "Sunday"]
        by_day: Dict[int, List[float]] = defaultdict(list)
        for t in trades:
            entry = t.get("entry_time")
            pnl = t.get("pnl", 0) or 0
            if isinstance(entry, str):
                try:
                    entry = datetime.fromisoformat(entry)
                except (ValueError, TypeError):
                    continue
            if isinstance(entry, datetime):
                by_day[entry.weekday()].append(pnl)

        results: Dict[str, Any] = {}
        for dow, pnls in sorted(by_day.items()):
            if len(pnls) >= min_sample:
                arr = np.array(pnls)
                results[day_names[dow]] = {
                    "n": len(pnls),
                    "avg_pnl": round(float(arr.mean()), 2),
                    "win_rate": round(float(np.sum(arr > 0) / len(arr)), 3),
                    "total": round(float(arr.sum()), 2),
                }
        return results

    def _regime_patterns(
        self, trades: List[Dict[str, Any]], min_sample: int,
    ) -> Dict[str, Any]:
        """Analyse P&L by market regime."""
        by_regime: Dict[str, List[float]] = defaultdict(list)
        for t in trades:
            regime = t.get("regime", "unknown") or "unknown"
            pnl = t.get("pnl", 0) or 0
            by_regime[regime].append(pnl)

        results: Dict[str, Any] = {}
        for regime, pnls in sorted(by_regime.items()):
            if len(pnls) >= min_sample:
                arr = np.array(pnls)
                results[regime] = {
                    "n": len(pnls),
                    "avg_pnl": round(float(arr.mean()), 2),
                    "win_rate": round(float(np.sum(arr > 0) / len(arr)), 3),
                    "total": round(float(arr.sum()), 2),
                    "sharpe": round(
                        float(arr.mean() / arr.std()) if arr.std() > 0 else 0.0, 2
                    ),
                }
        return results

    def _streak_analysis(self, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyse winning and losing streaks."""
        pnls = [t.get("pnl", 0) or 0 for t in trades]
        if not pnls:
            return {}

        max_win_streak = 0
        max_loss_streak = 0
        current_win = 0
        current_loss = 0
        win_streaks: List[int] = []
        loss_streaks: List[int] = []

        for pnl in pnls:
            if pnl > 0:
                current_win += 1
                if current_loss > 0:
                    loss_streaks.append(current_loss)
                current_loss = 0
            elif pnl < 0:
                current_loss += 1
                if current_win > 0:
                    win_streaks.append(current_win)
                current_win = 0

        if current_win > 0:
            win_streaks.append(current_win)
        if current_loss > 0:
            loss_streaks.append(current_loss)

        return {
            "max_win_streak": max(win_streaks) if win_streaks else 0,
            "max_loss_streak": max(loss_streaks) if loss_streaks else 0,
            "avg_win_streak": round(float(np.mean(win_streaks)), 1) if win_streaks else 0,
            "avg_loss_streak": round(float(np.mean(loss_streaks)), 1) if loss_streaks else 0,
        }

    def _exit_reason_patterns(
        self, trades: List[Dict[str, Any]], min_sample: int,
    ) -> Dict[str, Any]:
        """Analyse outcomes by exit reason."""
        by_exit: Dict[str, List[float]] = defaultdict(list)
        for t in trades:
            reason = t.get("exit_reason", "unknown") or "unknown"
            pnl = t.get("pnl", 0) or 0
            by_exit[reason].append(pnl)

        results: Dict[str, Any] = {}
        for reason, pnls in sorted(by_exit.items()):
            if len(pnls) >= max(3, min_sample // 3):
                arr = np.array(pnls)
                results[reason] = {
                    "n": len(pnls),
                    "avg_pnl": round(float(arr.mean()), 2),
                    "win_rate": round(float(np.sum(arr > 0) / len(arr)), 3),
                }
        return results

    def _r_multiple_analysis(self, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyse R-multiple distribution."""
        r_vals = [t.get("r_multiple") for t in trades if t.get("r_multiple") is not None]
        if len(r_vals) < 5:
            return {}

        arr = np.array(r_vals, dtype=float)
        return {
            "mean_r": round(float(arr.mean()), 2),
            "median_r": round(float(np.median(arr)), 2),
            "std_r": round(float(arr.std()), 2),
            "pct_above_1r": round(float(np.sum(arr >= 1) / len(arr)), 3),
            "pct_above_2r": round(float(np.sum(arr >= 2) / len(arr)), 3),
            "pct_below_neg1r": round(float(np.sum(arr <= -1) / len(arr)), 3),
        }
