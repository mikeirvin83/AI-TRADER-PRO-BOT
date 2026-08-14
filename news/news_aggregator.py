"""News aggregator — combines multiple news sources into a unified stream.

Merges Alpaca News API output with free RSS feeds, deduplicates by content
hash, classifies each item, and produces a ranked list of market-relevant
news with sentiment and impact scores.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

from config.logging_config import get_logger
from news.news_classifier import NewsClassifier
from news.news_fetcher import NewsFetcher
from news.rss_fetcher import RSSFetcher

log = get_logger(__name__)


class NewsItem:
    """Normalised news item with classification."""

    __slots__ = (
        "headline", "summary", "url", "source", "published_at",
        "content_hash", "symbols", "sentiment", "sentiment_score",
        "impact", "relevance_score",
    )

    def __init__(
        self,
        headline: str,
        summary: str = "",
        url: str = "",
        source: str = "",
        published_at: Optional[datetime] = None,
        content_hash: str = "",
        symbols: Optional[List[str]] = None,
    ):
        self.headline = headline
        self.summary = summary
        self.url = url
        self.source = source
        self.published_at = published_at or datetime.now(timezone.utc)
        self.content_hash = content_hash
        self.symbols = symbols or []
        self.sentiment = "neutral"
        self.sentiment_score = 0.0
        self.impact = "low"
        self.relevance_score = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "headline": self.headline,
            "summary": self.summary[:500],
            "url": self.url,
            "source": self.source,
            "published_at": self.published_at.isoformat(),
            "symbols": self.symbols,
            "sentiment": self.sentiment,
            "sentiment_score": self.sentiment_score,
            "impact": self.impact,
            "relevance_score": self.relevance_score,
        }


# Keywords that indicate a news item is relevant to our trading universe
_MARKET_KEYWORDS = {
    "spy", "qqq", "s&p", "nasdaq", "dow", "russell",
    "fed", "fomc", "interest rate", "inflation", "cpi", "ppi",
    "gdp", "jobs", "unemployment", "payroll", "retail sales",
    "earnings", "revenue", "guidance", "beat", "miss",
    "futures", "options", "volatility", "vix",
    "treasury", "bond", "yield", "recession",
    "aapl", "msft", "nvda", "amzn", "meta", "tsla", "googl",
    "bitcoin", "btc", "ethereum", "eth", "crypto",
}


def _compute_relevance(item: NewsItem, watch_symbols: Set[str]) -> float:
    """Score 0..1 how relevant a news item is to our trading activity."""
    text = f"{item.headline} {item.summary}".lower()
    score = 0.0

    # Direct symbol mention
    for sym in watch_symbols:
        if sym.lower() in text:
            score += 0.3
            break

    # Market keyword hits
    hits = sum(1 for kw in _MARKET_KEYWORDS if kw in text)
    score += min(0.4, hits * 0.08)

    # Impact boost
    if item.impact == "high":
        score += 0.2
    elif item.impact == "medium":
        score += 0.1

    # Recency boost (last 30 minutes)
    age = (datetime.now(timezone.utc) - item.published_at).total_seconds()
    if age < 1800:
        score += 0.1

    return min(1.0, round(score, 3))


class NewsAggregator:
    """Aggregates news from Alpaca + RSS, classifies, scores, and ranks."""

    def __init__(
        self,
        watch_symbols: Optional[List[str]] = None,
        max_age_hours: int = 24,
    ) -> None:
        self.classifier = NewsClassifier()
        self.alpaca_fetcher = NewsFetcher()
        self.rss_fetcher = RSSFetcher()
        self.watch_symbols: Set[str] = set(watch_symbols or [])
        self.max_age = timedelta(hours=max_age_hours)
        self._seen: Set[str] = set()

    def fetch_and_classify(
        self,
        symbols: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[NewsItem]:
        """Fetch from all sources, classify, score, and return ranked items."""
        raw_items: List[Dict[str, Any]] = []

        # 1. Alpaca News API (if credentials available)
        alpaca_syms = list(symbols or self.watch_symbols)
        if alpaca_syms:
            alpaca_items = self.alpaca_fetcher.fetch(alpaca_syms, limit=limit)
            for ai in alpaca_items:
                raw_items.append({
                    "headline": ai.get("headline", ""),
                    "summary": ai.get("summary", ""),
                    "url": ai.get("url", ""),
                    "source": "alpaca",
                    "published_at": ai.get("created_at", datetime.now(timezone.utc)),
                    "content_hash": ai.get("id", ""),
                    "symbols": ai.get("symbols", []),
                })

        # 2. RSS feeds (always available, no API key needed)
        rss_items = self.rss_fetcher.fetch_all(limit_per_feed=20)
        for ri in rss_items:
            raw_items.append({
                "headline": ri["headline"],
                "summary": ri.get("summary", ""),
                "url": ri.get("url", ""),
                "source": ri.get("source", "rss"),
                "published_at": ri.get("published_at", datetime.now(timezone.utc)),
                "content_hash": ri.get("content_hash", ""),
                "symbols": [],
            })

        # Deduplicate and normalise
        cutoff = datetime.now(timezone.utc) - self.max_age
        items: List[NewsItem] = []
        for raw in raw_items:
            h = raw.get("content_hash", "")
            if h in self._seen:
                continue
            self._seen.add(h)

            pub = raw.get("published_at")
            if isinstance(pub, str):
                try:
                    pub = datetime.fromisoformat(pub)
                except (ValueError, TypeError):
                    pub = datetime.now(timezone.utc)
            if pub and pub.tzinfo is None:
                pub = pub.replace(tzinfo=timezone.utc)
            if pub and pub < cutoff:
                continue

            item = NewsItem(
                headline=raw["headline"],
                summary=raw.get("summary", ""),
                url=raw.get("url", ""),
                source=raw.get("source", ""),
                published_at=pub or datetime.now(timezone.utc),
                content_hash=h,
                symbols=raw.get("symbols", []),
            )

            # Classify sentiment + impact
            cls = self.classifier.classify(item.headline, item.summary)
            item.sentiment = cls.sentiment
            item.sentiment_score = cls.sentiment_score
            item.impact = cls.impact

            # Compute relevance
            item.relevance_score = _compute_relevance(item, self.watch_symbols)

            items.append(item)

        # Sort by relevance * recency
        items.sort(key=lambda x: x.relevance_score, reverse=True)
        log.info("news_aggregated", total=len(items),
                 high_impact=sum(1 for i in items if i.impact == "high"))
        return items[:limit]

    def market_sentiment_summary(self, items: Optional[List[NewsItem]] = None) -> Dict[str, Any]:
        """Produce a market sentiment summary from recent news."""
        if items is None:
            items = self.fetch_and_classify()
        if not items:
            return {"overall": "neutral", "score": 0.0, "count": 0, "high_impact_count": 0}

        scores = [i.sentiment_score for i in items]
        avg = sum(scores) / len(scores) if scores else 0.0
        overall = "neutral"
        if avg > 0.15:
            overall = "bullish"
        elif avg < -0.15:
            overall = "bearish"

        return {
            "overall": overall,
            "score": round(avg, 3),
            "count": len(items),
            "high_impact_count": sum(1 for i in items if i.impact == "high"),
            "bullish": sum(1 for i in items if i.sentiment == "bullish"),
            "bearish": sum(1 for i in items if i.sentiment == "bearish"),
            "neutral": sum(1 for i in items if i.sentiment == "neutral"),
        }

    def reset(self) -> None:
        self._seen.clear()
        self.rss_fetcher.reset_dedup()
