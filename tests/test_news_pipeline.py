"""Tests for Phase 7 — News Intelligence Pipeline."""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import pytest

from news.rss_fetcher import RSSFetcher, _clean_html, _item_id, _parse_rss_date
from news.news_aggregator import NewsAggregator, NewsItem, _compute_relevance
from news.news_pipeline import NewsPipeline
from news.news_classifier import NewsClassifier
from news.economic_calendar import EconomicCalendar, EconomicEventDTO


# ------------------------------------------------------------------ #
# RSS Fetcher
# ------------------------------------------------------------------ #

class TestRSSFetcher:
    def test_clean_html(self):
        assert _clean_html("<p>Hello <b>world</b></p>") == "Hello world"
        assert _clean_html("No tags here") == "No tags here"
        assert _clean_html("") == ""

    def test_parse_rss_date_valid(self):
        dt = _parse_rss_date("2024-06-15T10:30:00Z")
        assert dt is not None
        assert dt.year == 2024
        assert dt.month == 6

    def test_parse_rss_date_invalid(self):
        assert _parse_rss_date("") is None
        assert _parse_rss_date("not a date") is None

    def test_item_id_deterministic(self):
        id1 = _item_id("Stock surges", "https://example.com/1")
        id2 = _item_id("Stock surges", "https://example.com/1")
        assert id1 == id2

    def test_item_id_case_insensitive_headline(self):
        id1 = _item_id("Stock SURGES", "https://example.com/1")
        id2 = _item_id("stock surges", "https://example.com/1")
        assert id1 == id2

    def test_dedup_reset(self):
        fetcher = RSSFetcher(feeds={})
        fetcher._seen_ids.add("test")
        assert len(fetcher._seen_ids) == 1
        fetcher.reset_dedup()
        assert len(fetcher._seen_ids) == 0


# ------------------------------------------------------------------ #
# News Classifier
# ------------------------------------------------------------------ #

class TestNewsClassifier:
    def test_bullish_headline(self):
        c = NewsClassifier()
        result = c.classify("Stock surges to record high, beating expectations")
        assert result.sentiment == "bullish"
        assert result.sentiment_score > 0

    def test_bearish_headline(self):
        c = NewsClassifier()
        result = c.classify("Company plunges after earnings miss, weak guidance")
        assert result.sentiment == "bearish"
        assert result.sentiment_score < 0

    def test_neutral_headline(self):
        c = NewsClassifier()
        result = c.classify("Company releases quarterly report today")
        assert result.sentiment == "neutral"

    def test_high_impact_keywords(self):
        c = NewsClassifier()
        result = c.classify("Fed raises interest rate by 25 basis points")
        assert result.impact == "high"

    def test_low_impact(self):
        c = NewsClassifier()
        result = c.classify("Company hires new marketing director")
        assert result.impact == "low"


# ------------------------------------------------------------------ #
# News Aggregator
# ------------------------------------------------------------------ #

class TestNewsAggregator:
    def test_news_item_to_dict(self):
        item = NewsItem(
            headline="Test headline",
            summary="Test summary",
            source="test",
            published_at=datetime(2024, 6, 15, tzinfo=timezone.utc),
        )
        d = item.to_dict()
        assert d["headline"] == "Test headline"
        assert d["source"] == "test"
        assert "published_at" in d

    def test_relevance_scoring_with_symbol(self):
        item = NewsItem(
            headline="AAPL stock surges after earnings beat",
            published_at=datetime.now(timezone.utc),
        )
        item.impact = "high"
        score = _compute_relevance(item, {"AAPL", "MSFT"})
        assert score > 0.3  # Symbol mention + high impact

    def test_relevance_scoring_no_match(self):
        item = NewsItem(
            headline="Weather report for weekend",
            published_at=datetime.now(timezone.utc) - timedelta(hours=2),
        )
        item.impact = "low"
        score = _compute_relevance(item, {"AAPL"})
        assert score < 0.2

    def test_market_sentiment_summary_empty(self):
        agg = NewsAggregator()
        summary = agg.market_sentiment_summary([])
        assert summary["overall"] == "neutral"
        assert summary["count"] == 0

    def test_market_sentiment_summary_bullish(self):
        agg = NewsAggregator()
        items = []
        for i in range(5):
            item = NewsItem(headline=f"Stock {i} surges")
            item.sentiment = "bullish"
            item.sentiment_score = 0.5
            items.append(item)
        summary = agg.market_sentiment_summary(items)
        assert summary["overall"] == "bullish"
        assert summary["bullish"] == 5

    def test_aggregator_reset(self):
        agg = NewsAggregator()
        agg._seen.add("test")
        agg.reset()
        assert len(agg._seen) == 0


# ------------------------------------------------------------------ #
# Economic Calendar
# ------------------------------------------------------------------ #

class TestEconomicCalendar:
    def test_blackout_window(self):
        cal = EconomicCalendar(blackout_minutes=15)
        event_time = datetime(2024, 6, 15, 14, 30, tzinfo=timezone.utc)
        cal.load([EconomicEventDTO("CPI", event_time, "high")])
        # Within blackout
        at = event_time + timedelta(minutes=5)
        assert cal.risk_state(at) == "blackout"

    def test_elevated_window(self):
        cal = EconomicCalendar(blackout_minutes=15, elevated_minutes=60)
        event_time = datetime(2024, 6, 15, 14, 30, tzinfo=timezone.utc)
        cal.load([EconomicEventDTO("CPI", event_time, "high")])
        # Within elevated but outside blackout
        at = event_time + timedelta(minutes=30)
        assert cal.risk_state(at) == "elevated"

    def test_normal_state(self):
        cal = EconomicCalendar()
        event_time = datetime(2024, 6, 15, 14, 30, tzinfo=timezone.utc)
        cal.load([EconomicEventDTO("CPI", event_time, "high")])
        # Well outside any window
        at = event_time + timedelta(hours=3)
        assert cal.risk_state(at) == "normal"

    def test_next_high_impact(self):
        cal = EconomicCalendar()
        t1 = datetime(2024, 6, 15, 14, 30, tzinfo=timezone.utc)
        t2 = datetime(2024, 6, 16, 14, 30, tzinfo=timezone.utc)
        cal.load([
            EconomicEventDTO("CPI", t1, "high"),
            EconomicEventDTO("PPI", t2, "high"),
        ])
        at = t1 + timedelta(hours=1)
        nxt = cal.next_high_impact(at)
        assert nxt is not None
        assert nxt.name == "PPI"


# ------------------------------------------------------------------ #
# News Pipeline
# ------------------------------------------------------------------ #

class TestNewsPipeline:
    def test_pipeline_creation(self):
        pipe = NewsPipeline(watch_symbols=["SPY", "QQQ"])
        assert not pipe._running

    def test_assess_trade_risk_no_news(self):
        pipe = NewsPipeline(watch_symbols=["SPY"])
        risk = pipe.assess_trade_risk("SPY", "LONG")
        assert risk["risk_state"] in ("normal", "elevated", "blackout")
        assert "calendar_risk" in risk
        assert "contradicts_direction" in risk

    def test_load_economic_events(self):
        pipe = NewsPipeline()
        events = [
            {"name": "CPI", "event_time": datetime(2024, 6, 15, 14, 30, tzinfo=timezone.utc),
             "importance": "high"},
        ]
        pipe.load_economic_events(events)
        # Should not raise

    def test_get_recent_news_empty(self):
        pipe = NewsPipeline()
        news = pipe.get_recent_news()
        assert isinstance(news, list)

    def test_market_sentiment_no_data(self):
        pipe = NewsPipeline()
        sentiment = pipe.get_market_sentiment()
        assert "overall" in sentiment
