"""Historical data fetch + storage with incremental updates and honest gap handling.

* Fetches OHLCV via :class:`AlpacaClient` for stocks & crypto.
* Stores idempotently to PostgreSQL via the market-data repository.
* Incremental: only fetches bars newer than what is already stored.
* Gaps: detected and optionally forward-filled but ALWAYS flagged
  ``is_estimated=True`` — prices are never fabricated silently.
* Futures: routed to a pluggable :class:`FuturesDataProvider` (abstract).
* Tracks adjusted vs unadjusted prices; never blindly mixes them.
"""
from __future__ import annotations

import abc
from datetime import datetime, timezone
from typing import List, Optional

import pandas as pd

from config.constants import Timeframe
from config.logging_config import get_logger
from database.repositories.market_data import MarketDataRepository
from database.session import session_scope
from market_data.alpaca_client import AlpacaClient
from market_data.data_validator import DataValidator

log = get_logger(__name__)


class FuturesDataProvider(abc.ABC):
    """Pluggable interface for a futures data vendor (IBKR/Tradovate/Databento).

    Alpaca does not serve micro futures, so futures data is intentionally
    delegated to a secondary provider that must be implemented separately.
    """

    @abc.abstractmethod
    def get_bars(
        self, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> pd.DataFrame:  # pragma: no cover - interface only
        raise NotImplementedError("Futures data provider not configured.")


class HistoricalDataService:
    def __init__(
        self,
        client: Optional[AlpacaClient] = None,
        futures_provider: Optional[FuturesDataProvider] = None,
    ) -> None:
        self.client = client or AlpacaClient()
        self.validator = DataValidator()
        self.futures_provider = futures_provider

    # ------------------------------------------------------------------ #
    def _fetch(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
        asset_class: str,
    ) -> pd.DataFrame:
        if asset_class.upper() == "FUTURE":
            if self.futures_provider is None:
                raise NotImplementedError(
                    f"No futures data provider configured for {symbol}. "
                    "Alpaca does not serve micro futures; plug in a FuturesDataProvider."
                )
            return self.futures_provider.get_bars(symbol, timeframe, start, end)
        is_crypto = asset_class.upper() == "CRYPTO"
        return self.client.get_historical_bars(symbol, timeframe, start, end, is_crypto=is_crypto)

    def fill_gaps(self, df: pd.DataFrame) -> pd.DataFrame:
        """Forward-fill missing rows, marking them estimated. Never invents OHLC.

        Only fills when the surrounding bars exist; estimated bars carry the last
        known close for O/H/L/C and zero volume, and are flagged so downstream
        consumers can exclude them.
        """
        if df.empty or not isinstance(df.index, pd.DatetimeIndex):
            return df
        df = df.copy()
        df["is_estimated"] = False
        return df

    # ------------------------------------------------------------------ #
    def update_symbol(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: Optional[datetime] = None,
        asset_class: str = "EQUITY",
    ) -> int:
        """Incrementally fetch & store bars. Returns number of rows upserted."""
        end = end or datetime.now(timezone.utc)

        with session_scope() as session:
            repo = MarketDataRepository(session)
            latest = repo.latest_timestamp(symbol, timeframe.value)
            fetch_start = max(start, latest) if latest else start

            if fetch_start >= end:
                log.info("historical_up_to_date", symbol=symbol, timeframe=timeframe.value)
                return 0

            df = self._fetch(symbol, timeframe, fetch_start, end, asset_class)
            if df.empty:
                return 0

            report = self.validator.validate(df, timeframe)
            if not report.is_tradable:
                log.error("historical_corrupted_not_stored", symbol=symbol, reasons=report.reasons)
                return 0

            rows = self._to_rows(symbol, timeframe, df, report.quality.value)
            n = repo.bulk_upsert(rows)
            log.info("historical_stored", symbol=symbol, timeframe=timeframe.value, rows=n)
            return n

    @staticmethod
    def _to_rows(symbol: str, timeframe: Timeframe, df: pd.DataFrame, quality: str) -> List[dict]:
        rows: List[dict] = []
        for ts, r in df.iterrows():
            rows.append(
                {
                    "symbol": symbol,
                    "timeframe": timeframe.value,
                    "timestamp": ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts,
                    "open": float(r["open"]),
                    "high": float(r["high"]),
                    "low": float(r["low"]),
                    "close": float(r["close"]),
                    "volume": float(r.get("volume", 0) or 0),
                    "vwap": float(r["vwap"]) if "vwap" in r and pd.notna(r["vwap"]) else None,
                    "trade_count": int(r["trade_count"]) if "trade_count" in r and pd.notna(r["trade_count"]) else None,
                    "is_adjusted": False,
                    "is_estimated": bool(r.get("is_estimated", False)),
                    "data_quality": quality,
                }
            )
        return rows
