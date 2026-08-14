"""Tests for Phase 8 — LLM/AI Memory & Learning Integration."""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pytest

from memory.strategy_learner import StrategyLearner
from memory.pattern_detector import PatternDetector
from memory.llm_analyzer import LLMAnalyzer


# ------------------------------------------------------------------ #
# Strategy Learner
# ------------------------------------------------------------------ #

class TestStrategyLearner:
    def test_insufficient_trades_skip(self):
        learner = StrategyLearner()
        # Less than 10 trades — should return empty
        proposals = learner.analyze_and_propose(
            strategy_name="test_strat",
            trade_pnls=[100, -50, 200],
            strategy_params={},
        )
        assert proposals == []

    def test_compute_statistics(self):
        learner = StrategyLearner()
        pnls = [100, -50, 200, -30, 150, -80, 120, -40, 90, -60,
                110, -20, 80, -70, 130]
        stats = learner._compute_statistics(pnls)
        assert stats["n_trades"] == 15
        assert 0 < stats["win_rate"] < 1
        assert stats["total_pnl"] == sum(pnls)
        assert stats["max_consecutive_losses"] >= 1
        assert stats["max_consecutive_wins"] >= 1

    def test_detect_drift_no_drift(self):
        learner = StrategyLearner()
        live = {"win_rate": 0.55, "sharpe": 1.2, "profit_factor": 1.5, "max_drawdown": 1000}
        bt = {"win_rate": 0.56, "sharpe": 1.3, "profit_factor": 1.6, "max_drawdown": 900}
        drift = learner._detect_drift(live, bt)
        assert drift is None  # Within tolerance

    def test_detect_drift_significant(self):
        learner = StrategyLearner()
        live = {"win_rate": 0.30, "sharpe": 0.3, "profit_factor": 0.8, "max_drawdown": 5000}
        bt = {"win_rate": 0.55, "sharpe": 1.5, "profit_factor": 1.8, "max_drawdown": 1000}
        drift = learner._detect_drift(live, bt)
        assert drift is not None
        assert len(drift["reasons"]) >= 2  # Multiple drifts

    def test_suggest_parameters_low_winrate(self):
        learner = StrategyLearner()
        stats = {
            "win_rate": 0.2,  # Very low
            "max_consecutive_losses": 5,
            "profit_factor": 1.5,
        }
        params = {"min_signal_score": 75, "risk_per_trade_pct": 0.01}
        suggestions = learner._suggest_parameters(stats, params)
        assert "min_signal_score" in suggestions
        assert suggestions["min_signal_score"] > 75

    def test_suggest_parameters_high_consec_losses(self):
        learner = StrategyLearner()
        stats = {
            "win_rate": 0.5,
            "max_consecutive_losses": 10,
            "profit_factor": 1.5,
        }
        params = {"risk_per_trade_pct": 0.01}
        suggestions = learner._suggest_parameters(stats, params)
        assert "risk_per_trade_pct" in suggestions
        assert suggestions["risk_per_trade_pct"] < 0.01

    def test_suggest_parameters_weak_pf(self):
        learner = StrategyLearner()
        stats = {
            "win_rate": 0.5,
            "max_consecutive_losses": 3,
            "profit_factor": 1.05,  # Very weak
        }
        params = {"stop_loss_atr_mult": 2.0}
        suggestions = learner._suggest_parameters(stats, params)
        assert "stop_loss_atr_mult" in suggestions
        assert suggestions["stop_loss_atr_mult"] < 2.0

    def test_regime_fit_concentrated(self):
        learner = StrategyLearner()
        regime_dist = {"STRONG_UPTREND": 80, "RANGE_BOUND": 10, "CHOPPY": 10}
        result = learner._analyze_regime_fit(
            "test", regime_dist, list(range(100)))
        assert result is not None
        assert result["dominant_regime"] == "STRONG_UPTREND"

    def test_regime_fit_balanced(self):
        learner = StrategyLearner()
        regime_dist = {"STRONG_UPTREND": 30, "RANGE_BOUND": 35, "CHOPPY": 35}
        result = learner._analyze_regime_fit(
            "test", regime_dist, list(range(100)))
        assert result is None  # Not concentrated enough


# ------------------------------------------------------------------ #
# Pattern Detector
# ------------------------------------------------------------------ #

class TestPatternDetector:
    def _make_trades(self, n: int) -> list:
        trades = []
        for i in range(n):
            pnl = 100 if i % 3 != 0 else -50
            trades.append({
                "symbol": "SPY",
                "pnl": pnl,
                "entry_time": datetime(2024, 6, 1 + (i % 28), 10 + (i % 7),
                                       0, tzinfo=timezone.utc),
                "regime": "STRONG_UPTREND" if i % 2 == 0 else "RANGE_BOUND",
                "exit_reason": "target" if pnl > 0 else "stop_loss",
                "r_multiple": pnl / 50,
            })
        return trades

    def test_insufficient_data(self):
        det = PatternDetector()
        result = det.analyze([], min_sample=10)
        assert result["status"] == "insufficient_data"

    def test_full_analysis(self):
        det = PatternDetector()
        trades = self._make_trades(50)
        result = det.analyze(trades, min_sample=5)
        assert result["n_trades"] == 50
        assert "time_patterns" in result
        assert "day_patterns" in result
        assert "regime_patterns" in result
        assert "streak_patterns" in result

    def test_streak_analysis(self):
        det = PatternDetector()
        trades = [{"pnl": 100}] * 5 + [{"pnl": -50}] * 3 + [{"pnl": 80}] * 2
        result = det._streak_analysis(trades)
        assert result["max_win_streak"] == 5
        assert result["max_loss_streak"] == 3

    def test_exit_reason_patterns(self):
        det = PatternDetector()
        trades = (
            [{"exit_reason": "target", "pnl": 100}] * 10
            + [{"exit_reason": "stop_loss", "pnl": -50}] * 5
        )
        result = det._exit_reason_patterns(trades, min_sample=3)
        assert "target" in result
        assert result["target"]["n"] == 10

    def test_r_multiple_analysis(self):
        det = PatternDetector()
        trades = [{"r_multiple": r} for r in [2.0, 1.5, -0.5, 3.0, -1.0, 0.5, 1.0]]
        result = det._r_multiple_analysis(trades)
        assert "mean_r" in result
        assert "pct_above_1r" in result


# ------------------------------------------------------------------ #
# LLM Analyzer (graceful degradation without API key)
# ------------------------------------------------------------------ #

class TestLLMAnalyzer:
    def test_unavailable_without_key(self):
        """LLM analyzer should not crash without API key."""
        analyzer = LLMAnalyzer()
        # With no ABACUSAI_API_KEY, it should be unavailable
        # and return None gracefully
        result = analyzer.analyze_trade_batch([])
        assert result is None

    def test_evaluate_strategy_graceful(self):
        analyzer = LLMAnalyzer()
        result = analyzer.evaluate_strategy_performance(
            "test", {"sharpe": 1.5}, [])
        assert result is None  # No key configured

    def test_parse_json_valid(self):
        result = LLMAnalyzer._parse_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_parse_json_with_markdown(self):
        raw = 'Here is the analysis:\n```json\n{"key": "value"}\n```\nDone.'
        result = LLMAnalyzer._parse_json(raw)
        assert result == {"key": "value"}

    def test_parse_json_embedded(self):
        raw = 'Analysis: {"key": "value"} end'
        result = LLMAnalyzer._parse_json(raw)
        assert result == {"key": "value"}

    def test_parse_json_none(self):
        assert LLMAnalyzer._parse_json(None) is None
