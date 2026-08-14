"""Tests for the enhanced weekly review."""
import pytest
from orchestration.weekly_review import WeeklyReview


class TestWeeklyReview:
    def test_run_with_profiles(self):
        review = WeeklyReview()
        profiles = [
            {
                "name": "ema_crossover",
                "category": "trend",
                "status": "ACTIVE",
                "trade_pnls": [100, -50, 200, 150, -30, 80, 120] * 10,
                "sharpe": 1.2,
                "max_drawdown": 0.08,
                "profit_factor": 2.0,
                "win_rate": 0.6,
                "correlation_score": 0.1,
            },
            {
                "name": "rsi_reversion",
                "category": "mean_reversion",
                "status": "WATCH",
                "trade_pnls": [-50, 30, -100, -80, 20, -60] * 5,
                "sharpe": -0.3,
                "max_drawdown": 0.20,
                "profit_factor": 0.6,
                "win_rate": 0.35,
                "correlation_score": 0.3,
            },
        ]
        result = review.run(profiles)
        assert result["n_strategies"] == 2
        assert "degradation_reports" in result
        assert "allocation" in result
        assert result["allocation"]["cash_reserve"] > 0

    def test_run_empty(self):
        review = WeeklyReview()
        result = review.run([])
        assert result["n_strategies"] == 0
