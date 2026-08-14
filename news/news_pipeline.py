"""News intelligence pipeline — orchestrates fetching, classification, and
event generation for the trading decision loop.

This is the "live" news system that integrates with the event bus so that
news events can influence trade decisions in real time.

Capabilities:
  - Periodic polling of all news sources (Alpaca + RSS)
  - High-impact news detection → publishes NEWS_EVENT on event bus
  - Pre-trade news risk assessment
  - Economic calendar risk state integration
  - Market sentiment tracking over rolling windows
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from config.constants import EventTopic
from config.logging_config import get_logger
from core.event_bus import Event, get_event_bus
from news.economic_calendar import EconomicCalendar, EconomicEventDTO
from news.news_aggregator import NewsAggregator, NewsItem

log = get_logger(__name__)


class NewsPipeline:
    """Orchestrates the news intelligence layer.

    Runs as an async background task, polling news at a configurable interval
    and publishing high-impact events to the event bus.
    """

    def __init__(
        self,
        watch_symbols: Optional[List[str]] = None,
        poll_interval_seconds: int = 300,  # 5 minutes default
        high_impact_threshold: float = 0.5,
    ) -> None:
        self.aggregator = NewsAggregator(watch_symbols=watch_symbols)
        self.calendar = EconomicCalendar()
        self._bus = get_event_bus()
        self.poll_interval = poll_interval_seconds
        self.high_impact_threshold = high_impact_threshold
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._recent_items: List[NewsItem] = []
        self._sentiment_history: List[Dict[str, Any]] = []  # rolling sentiment

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    async def start(self) -> None:
        """Start the background polling loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        log.info("news_pipeline_started", interval=self.poll_interval)

    async def stop(self) -> None:
        """Stop the background polling loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        log.info("news_pipeline_stopped")

    def assess_trade_risk(
        self, symbol: str, direction: str,
    ) -> Dict[str, Any]:
        """Assess news risk for a specific trade.

        Returns risk_state (normal/elevated/blackout), relevant news,
        and whether news contradicts the trade direction.
        """
        # Economic calendar risk
        cal_risk = self.calendar.risk_state()

        # Find relevant recent news for this symbol
        relevant = [
            item for item in self._recent_items
            if symbol.upper() in [s.upper() for s in item.symbols]
            or symbol.lower() in item.headline.lower()
        ]

        # Check sentiment contradiction
        contradicts = False
        if relevant:
            avg_sent = sum(i.sentiment_score for i in relevant) / len(relevant)
            if direction == "LONG" and avg_sent < -0.3:
                contradicts = True
            elif direction == "SHORT" and avg_sent > 0.3:
                contradicts = True

        # Determine overall risk state
        risk_state = cal_risk
        if any(i.impact == "high" for i in relevant):
            risk_state = max(risk_state, "elevated", key=lambda x: {
                "normal": 0, "elevated": 1, "blackout": 2}.get(x, 0))

        return {
            "risk_state": risk_state,
            "calendar_risk": cal_risk,
            "relevant_news_count": len(relevant),
            "contradicts_direction": contradicts,
            "sentiment": self._current_sentiment(),
            "next_high_impact_event": self._next_event_info(),
        }

    def get_market_sentiment(self) -> Dict[str, Any]:
        """Get current market sentiment from recent news."""
        return self._current_sentiment()

    def get_recent_news(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent news items."""
        return [item.to_dict() for item in self._recent_items[:limit]]

    def load_economic_events(self, events: List[Dict[str, Any]]) -> None:
        """Load economic events into the calendar."""
        dto_events = []
        for ev in events:
            et = ev.get("event_time")
            if isinstance(et, str):
                try:
                    et = datetime.fromisoformat(et)
                except (ValueError, TypeError):
                    continue
            dto_events.append(EconomicEventDTO(
                name=ev["name"],
                event_time=et,
                importance=ev.get("importance", "medium"),
            ))
        self.calendar.load(dto_events)
        log.info("economic_events_loaded", count=len(dto_events))

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #

    async def _poll_loop(self) -> None:
        """Background loop: fetch, classify, and publish events."""
        while self._running:
            try:
                await self._poll_once()
            except Exception:  # noqa: BLE001
                log.exception("news_poll_error")
            await asyncio.sleep(self.poll_interval)

    async def _poll_once(self) -> None:
        """Single poll iteration."""
        # Run I/O in thread to avoid blocking the event loop
        items = await asyncio.to_thread(
            self.aggregator.fetch_and_classify, limit=100
        )
        self._recent_items = items

        # Track sentiment over time
        sentiment = self.aggregator.market_sentiment_summary(items)
        sentiment["timestamp"] = datetime.now(timezone.utc).isoformat()
        self._sentiment_history.append(sentiment)
        # Keep last 288 entries (24h at 5-min intervals)
        self._sentiment_history = self._sentiment_history[-288:]

        # Publish high-impact items to event bus
        high_impact = [
            i for i in items
            if i.impact == "high" or i.relevance_score >= self.high_impact_threshold
        ]
        for item in high_impact:
            await self._bus.publish(Event(
                topic=EventTopic.NEWS_EVENT,
                payload=item.to_dict(),
                source="news_pipeline",
            ))

        log.info("news_poll_complete", items=len(items),
                 high_impact=len(high_impact), sentiment=sentiment.get("overall"))

    def _current_sentiment(self) -> Dict[str, Any]:
        """Return the latest sentiment summary."""
        if self._sentiment_history:
            return self._sentiment_history[-1]
        return self.aggregator.market_sentiment_summary(self._recent_items)

    def _next_event_info(self) -> Optional[Dict[str, str]]:
        """Return info about the next high-impact economic event."""
        ev = self.calendar.next_high_impact()
        if ev is None:
            return None
        return {"name": ev.name, "event_time": ev.event_time.isoformat(),
                "importance": ev.importance}
