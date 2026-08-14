"""LLM-powered trade and market analysis.

Uses structured prompts to extract insights from trade history, market
conditions, and strategy performance. All LLM calls are optional — the
system degrades gracefully if no LLM is configured.

This module does NOT make trading decisions. It produces analysis and
insights that feed into the learning engine as *proposals* requiring
approval before any parameter changes take effect.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config.logging_config import get_logger

log = get_logger(__name__)

# Best-effort import; LLM features are optional
try:
    from openai import OpenAI as _OpenAI
    _HAS_OPENAI = True
except ImportError:
    _HAS_OPENAI = False


def _get_client() -> Optional[Any]:
    """Create an OpenAI-compatible client pointing at the RouteLLM endpoint."""
    api_key = os.getenv("ABACUSAI_API_KEY", "")
    if not api_key or not _HAS_OPENAI:
        return None
    try:
        return _OpenAI(
            api_key=api_key,
            base_url="https://llmrouter.abacus.ai/v1",
        )
    except Exception:  # noqa: BLE001
        return None


def _chat(client: Any, system: str, user: str, max_tokens: int = 1024) -> Optional[str]:
    """Single-turn chat completion with error handling."""
    try:
        resp = client.chat.completions.create(
            model="claude-3-5-sonnet-20241022",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
            temperature=0.3,
        )
        return resp.choices[0].message.content
    except Exception as exc:  # noqa: BLE001
        log.warning("llm_call_failed", error=str(exc))
        return None


class LLMAnalyzer:
    """Stateless LLM-powered analysis functions."""

    def __init__(self) -> None:
        self._client = _get_client()
        self.available = self._client is not None

    # ------------------------------------------------------------------ #
    # Trade review
    # ------------------------------------------------------------------ #

    def analyze_trade_batch(
        self, trades: List[Dict[str, Any]], regime: str = "unknown",
    ) -> Optional[Dict[str, Any]]:
        """Analyse a batch of recent trades and return structured insights."""
        if not self.available:
            return None

        system = (
            "You are a quantitative trading analyst reviewing recent trades. "
            "Provide structured analysis in JSON with keys: "
            "patterns (list of observed patterns), "
            "winning_conditions (what worked), "
            "losing_conditions (what failed), "
            "regime_observations (how regime affected results), "
            "recommendations (list of actionable suggestions). "
            "Be specific and data-driven. Never fabricate statistics."
        )
        trade_summary = json.dumps(trades[:50], default=str, indent=1)
        user = (
            f"Market regime: {regime}\n"
            f"Recent trades ({len(trades)} total, showing up to 50):\n"
            f"{trade_summary}"
        )
        raw = _chat(self._client, system, user, max_tokens=1500)
        return self._parse_json(raw)

    # ------------------------------------------------------------------ #
    # Strategy evaluation
    # ------------------------------------------------------------------ #

    def evaluate_strategy_performance(
        self,
        strategy_name: str,
        metrics: Dict[str, Any],
        recent_trades: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """LLM-assisted strategy performance evaluation."""
        if not self.available:
            return None

        system = (
            "You are a quantitative strategy researcher. Evaluate the strategy "
            "performance and provide structured JSON with keys: "
            "health_assessment (one of: healthy/watch/degraded/critical), "
            "strengths (list), weaknesses (list), "
            "parameter_suggestions (dict of param -> suggested change), "
            "regime_suitability (list of regimes where strategy works best), "
            "risk_concerns (list). Be conservative — recommend changes only with "
            "clear evidence."
        )
        user = (
            f"Strategy: {strategy_name}\n"
            f"Metrics: {json.dumps(metrics, default=str)}\n"
            f"Recent trades: {json.dumps(recent_trades[:30], default=str)}"
        )
        raw = _chat(self._client, system, user, max_tokens=1200)
        return self._parse_json(raw)

    # ------------------------------------------------------------------ #
    # Market regime interpretation
    # ------------------------------------------------------------------ #

    def interpret_market_conditions(
        self,
        features: Dict[str, float],
        news_summary: Dict[str, Any],
        current_regime: str,
    ) -> Optional[Dict[str, Any]]:
        """Produce a human-readable market interpretation."""
        if not self.available:
            return None

        system = (
            "You are a market analyst. Given technical features, news sentiment, "
            "and the detected market regime, produce structured JSON with: "
            "market_narrative (1-2 sentence summary), "
            "key_drivers (list of factors driving current conditions), "
            "risk_factors (list), "
            "opportunity_areas (list of potential setups), "
            "caution_areas (list of things to avoid). "
            "Be factual — do not speculate beyond the data provided."
        )
        user = (
            f"Regime: {current_regime}\n"
            f"Technical features: {json.dumps(features, default=str)}\n"
            f"News sentiment: {json.dumps(news_summary, default=str)}"
        )
        raw = _chat(self._client, system, user, max_tokens=1000)
        return self._parse_json(raw)

    # ------------------------------------------------------------------ #
    # Pattern recognition from trade history
    # ------------------------------------------------------------------ #

    def detect_patterns(
        self, trade_history: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Detect recurring patterns in trade history."""
        if not self.available:
            return None

        system = (
            "You are a pattern recognition system analyzing trading history. "
            "Return structured JSON with: "
            "time_patterns (recurring time-of-day or day-of-week effects), "
            "regime_patterns (which regimes produce best/worst results), "
            "symbol_patterns (symbol-specific behaviors), "
            "loss_patterns (common loss scenarios), "
            "win_patterns (common win scenarios), "
            "correlation_patterns (correlated outcomes across strategies). "
            "Only report patterns supported by the data. Include counts."
        )
        user = (
            f"Trade history ({len(trade_history)} trades, showing up to 100):\n"
            f"{json.dumps(trade_history[:100], default=str, indent=1)}"
        )
        raw = _chat(self._client, system, user, max_tokens=1500)
        return self._parse_json(raw)

    # ------------------------------------------------------------------ #
    # News impact analysis
    # ------------------------------------------------------------------ #

    def analyze_news_impact(
        self,
        news_items: List[Dict[str, Any]],
        current_positions: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Analyze how current news might impact open positions."""
        if not self.available:
            return None

        system = (
            "You are a news-impact analyst for a trading system. Given recent "
            "news and open positions, return structured JSON with: "
            "position_risks (list of {symbol, risk_level, reason}), "
            "market_outlook (bullish/neutral/bearish with reasoning), "
            "action_items (list of suggested actions for the trading system). "
            "Be conservative — only flag genuine risks, not noise."
        )
        user = (
            f"Recent news: {json.dumps(news_items[:20], default=str)}\n"
            f"Open positions: {json.dumps(current_positions, default=str)}"
        )
        raw = _chat(self._client, system, user, max_tokens=1000)
        return self._parse_json(raw)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _parse_json(raw: Optional[str]) -> Optional[Dict[str, Any]]:
        """Best-effort extraction of JSON from LLM response."""
        if not raw:
            return None
        # Try direct parse
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        # Try extracting JSON block
        import re
        match = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", raw)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        # Try finding first { ... }
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start:end + 1])
            except json.JSONDecodeError:
                pass
        log.debug("llm_json_parse_failed", raw_length=len(raw))
        return {"raw_response": raw}
