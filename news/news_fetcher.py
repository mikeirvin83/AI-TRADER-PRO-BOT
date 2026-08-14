"""News fetcher — integrates with Alpaca News API (and pluggable providers).

Never fabricates headlines. If no provider/credentials are available it returns
an empty list rather than synthetic news.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from config.logging_config import get_logger
from config.settings import get_settings

log = get_logger(__name__)


class NewsFetcher:
    def __init__(self) -> None:
        self.creds = get_settings().resolve_alpaca_credentials()
        self._client = None
        try:
            from alpaca.data.historical.news import NewsClient  # type: ignore
            if self.creds["api_key"] and self.creds["secret_key"]:
                self._client = NewsClient(self.creds["api_key"], self.creds["secret_key"])
        except Exception:  # noqa: BLE001
            self._client = None

    def fetch(self, symbols: List[str], start: Optional[datetime] = None,
              end: Optional[datetime] = None, limit: int = 50) -> List[dict]:
        if self._client is None:
            log.warning("news_client_unavailable")
            return []
        from alpaca.data.requests import NewsRequest

        req = NewsRequest(symbols=",".join(symbols), start=start, end=end, limit=limit)
        try:
            resp = self._client.get_news(req)
            items = resp.data.get("news", []) if hasattr(resp, "data") else []
            return [getattr(n, "__dict__", n) for n in items]
        except Exception:  # noqa: BLE001
            log.exception("news_fetch_error")
            return []
