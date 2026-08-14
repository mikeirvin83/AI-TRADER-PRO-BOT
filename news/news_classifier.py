"""News classifier — lightweight lexicon sentiment + impact heuristic.

This is intentionally simple and transparent (no black-box model) for the
scaffold. It can be swapped for an ML classifier later via the same interface.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

_BULLISH = {"beat", "surge", "soar", "record", "upgrade", "growth", "strong",
            "rally", "gain", "outperform", "bullish", "raises", "tops"}
_BEARISH = {"miss", "plunge", "cut", "downgrade", "weak", "loss", "decline",
            "lawsuit", "probe", "bearish", "warns", "slump", "recall"}
_HIGH_IMPACT = {"fda", "earnings", "merger", "acquisition", "bankruptcy",
                "guidance", "sec", "fed", "rate", "cpi"}


@dataclass
class NewsClassification:
    sentiment: str          # bullish / bearish / neutral
    sentiment_score: float  # -1..1
    impact: str             # low / medium / high


class NewsClassifier:
    def classify(self, headline: str, summary: str = "") -> NewsClassification:
        text = f"{headline} {summary}".lower()
        tokens = set(text.replace(",", " ").replace(".", " ").split())
        bull = len(tokens & _BULLISH)
        bear = len(tokens & _BEARISH)
        total = bull + bear
        score = 0.0 if total == 0 else (bull - bear) / total
        sentiment = "neutral"
        if score > 0.15:
            sentiment = "bullish"
        elif score < -0.15:
            sentiment = "bearish"
        impact = "high" if tokens & _HIGH_IMPACT else ("medium" if total >= 2 else "low")
        return NewsClassification(sentiment, round(score, 3), impact)
