"""Free RSS-based news fetcher — no API keys required.

Fetches financial news from free RSS feeds (MarketWatch, Yahoo Finance,
Reuters, CNBC). Normalises items into a common dict format compatible
with the news pipeline.

Never fabricates headlines. Returns empty list when feeds are unreachable.
"""
from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

from config.logging_config import get_logger

log = get_logger(__name__)

# Free financial RSS feeds
DEFAULT_FEEDS: Dict[str, str] = {
    "marketwatch_top": "https://feeds.marketwatch.com/marketwatch/topstories/",
    "marketwatch_markets": "https://feeds.marketwatch.com/marketwatch/marketpulse/",
    "cnbc_markets": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258",
    "yahoo_finance": "https://finance.yahoo.com/news/rssindex",
    "investing_news": "https://www.investing.com/rss/news.rss",
}

_UA = "Mozilla/5.0 (compatible; TradingPlatform/1.0; +https://github.com/tradingbot)"


def _clean_html(text: str) -> str:
    """Strip HTML tags from summary text."""
    return re.sub(r"<[^>]+>", "", text).strip()


def _parse_rss_date(date_str: str) -> Optional[datetime]:
    """Parse RSS date string to timezone-aware datetime."""
    if not date_str:
        return None
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        pass
    # Try ISO format fallback
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def _item_id(headline: str, url: str) -> str:
    """Deterministic content hash for deduplication."""
    key = f"{headline.lower().strip()}|{url.strip()}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


class RSSFetcher:
    """Fetches news from RSS feeds with timeout and error handling."""

    def __init__(
        self,
        feeds: Optional[Dict[str, str]] = None,
        timeout_seconds: int = 10,
    ) -> None:
        self.feeds = feeds or DEFAULT_FEEDS
        self.timeout = timeout_seconds
        self._seen_ids: set = set()  # in-memory dedup within session

    def fetch_all(self, limit_per_feed: int = 20) -> List[Dict[str, Any]]:
        """Fetch from all configured feeds and return deduplicated items."""
        all_items: List[Dict[str, Any]] = []
        for feed_name, url in self.feeds.items():
            items = self._fetch_feed(feed_name, url, limit_per_feed)
            all_items.extend(items)
        # Deduplicate
        unique: List[Dict[str, Any]] = []
        for item in all_items:
            if item["content_hash"] not in self._seen_ids:
                self._seen_ids.add(item["content_hash"])
                unique.append(item)
        # Sort by published_at descending
        unique.sort(key=lambda x: x.get("published_at") or datetime.min.replace(tzinfo=timezone.utc),
                    reverse=True)
        return unique

    def _fetch_feed(self, name: str, url: str, limit: int) -> List[Dict[str, Any]]:
        """Fetch a single RSS feed, returning normalised items."""
        try:
            req = Request(url, headers={"User-Agent": _UA})
            with urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
        except (URLError, OSError, Exception) as exc:
            log.warning("rss_fetch_error", feed=name, error=str(exc))
            return []

        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            log.warning("rss_parse_error", feed=name)
            return []

        items: List[Dict[str, Any]] = []
        # Handle both RSS 2.0 and Atom
        rss_items = root.findall(".//item") or root.findall(
            ".//{http://www.w3.org/2005/Atom}entry"
        )

        for item_el in rss_items[:limit]:
            headline = self._el_text(item_el, "title") or ""
            link = self._el_text(item_el, "link") or ""
            summary = _clean_html(
                self._el_text(item_el, "description")
                or self._el_text(item_el, "summary")
                or ""
            )
            pub_str = (
                self._el_text(item_el, "pubDate")
                or self._el_text(item_el, "published")
                or self._el_text(item_el, "updated")
                or ""
            )
            published_at = _parse_rss_date(pub_str) or datetime.now(timezone.utc)

            if not headline:
                continue

            items.append({
                "headline": headline,
                "summary": summary[:1000],
                "url": link,
                "source": name,
                "published_at": published_at,
                "content_hash": _item_id(headline, link),
            })

        log.debug("rss_fetched", feed=name, items=len(items))
        return items

    @staticmethod
    def _el_text(parent, tag: str) -> Optional[str]:
        """Extract text from a child element, handling namespaces."""
        el = parent.find(tag)
        if el is None:
            # Try Atom namespace
            el = parent.find(f"{{http://www.w3.org/2005/Atom}}{tag}")
        if el is not None:
            # Atom link uses href attribute
            if tag == "link" and el.text is None:
                return el.get("href", "")
            return el.text or ""
        return None

    def reset_dedup(self) -> None:
        """Clear the deduplication set (e.g. between sessions)."""
        self._seen_ids.clear()
