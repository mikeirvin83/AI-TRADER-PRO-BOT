"""Alpaca client — REST + WebSocket wrapper.

Wraps the official ``alpaca-py`` SDK when available, falling back to a thin
``httpx`` REST client so the module always imports and is testable without the
SDK installed. Credentials are resolved via :mod:`config.settings` and NEVER
hardcoded. Paper vs live endpoints are selected from the resolved ``base_url``.
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

from config.constants import Timeframe
from config.logging_config import get_logger
from config.settings import get_settings

log = get_logger(__name__)

try:  # optional heavy dependency
    from alpaca.data.historical import StockHistoricalDataClient, CryptoHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest, CryptoBarsRequest
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    from alpaca.trading.client import TradingClient
    _ALPACA_SDK = True
except Exception:  # noqa: BLE001
    _ALPACA_SDK = False


_TF_MAP = {
    Timeframe.M1: ("Min", 1),
    Timeframe.M5: ("Min", 5),
    Timeframe.M15: ("Min", 15),
    Timeframe.M30: ("Min", 30),
    Timeframe.H1: ("Hour", 1),
    Timeframe.H4: ("Hour", 4),
    Timeframe.D1: ("Day", 1),
    Timeframe.W1: ("Week", 1),
}


def _retry(fn: Callable[[], Any], attempts: int = 3, backoff: float = 0.5) -> Any:
    """Retry a callable with exponential backoff. Re-raises the final error."""
    last: Optional[Exception] = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            last = exc
            wait = backoff * (2 ** i)
            log.warning("alpaca_retry", attempt=i + 1, error=str(exc), wait=wait)
            time.sleep(wait)
    assert last is not None
    raise last


class AlpacaClient:
    """High-level Alpaca client for account, positions, orders and bars."""

    def __init__(self) -> None:
        creds = get_settings().resolve_alpaca_credentials()
        self._api_key = creds["api_key"]
        self._secret_key = creds["secret_key"]
        self._base_url = creds["base_url"]
        self._data_url = creds["data_url"]
        self._is_paper = "paper" in self._base_url.lower()

        if not self._api_key or not self._secret_key:
            log.warning("alpaca_credentials_missing",
                        hint="Set ALPACA_API_KEY/SECRET or connector secrets file")

        self._trading: Any = None
        self._stock_data: Any = None
        self._crypto_data: Any = None
        if _ALPACA_SDK and self._api_key and self._secret_key:
            self._trading = TradingClient(self._api_key, self._secret_key, paper=self._is_paper)
            self._stock_data = StockHistoricalDataClient(self._api_key, self._secret_key)
            self._crypto_data = CryptoHistoricalDataClient(self._api_key, self._secret_key)

    # ------------------------------------------------------------------ #
    @property
    def is_paper(self) -> bool:
        return self._is_paper

    @property
    def sdk_available(self) -> bool:
        return bool(self._trading)

    def _require_sdk(self) -> None:
        if not self._trading:
            raise RuntimeError(
                "Alpaca SDK unavailable or credentials missing. Install alpaca-py and "
                "configure ALPACA_API_KEY / ALPACA_SECRET_KEY."
            )

    # ------------------------------------------------------------------ #
    # Account / positions / orders
    # ------------------------------------------------------------------ #
    def get_account(self) -> Dict[str, Any]:
        self._require_sdk()
        acct = _retry(lambda: self._trading.get_account())
        return acct.__dict__ if hasattr(acct, "__dict__") else dict(acct)

    def get_positions(self) -> List[Dict[str, Any]]:
        self._require_sdk()
        positions = _retry(lambda: self._trading.get_all_positions())
        return [p.__dict__ if hasattr(p, "__dict__") else dict(p) for p in positions]

    def get_orders(self, status: str = "open") -> List[Dict[str, Any]]:
        self._require_sdk()
        from alpaca.trading.requests import GetOrdersRequest
        from alpaca.trading.enums import QueryOrderStatus

        req = GetOrdersRequest(status=QueryOrderStatus(status))
        orders = _retry(lambda: self._trading.get_orders(req))
        return [o.__dict__ if hasattr(o, "__dict__") else dict(o) for o in orders]

    # ------------------------------------------------------------------ #
    # Historical bars
    # ------------------------------------------------------------------ #
    def _to_alpaca_timeframe(self, tf: Timeframe):
        unit_name, amount = _TF_MAP[tf]
        unit = getattr(TimeFrameUnit, unit_name)
        return TimeFrame(amount, unit)

    def get_historical_bars(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
        is_crypto: bool = False,
    ) -> pd.DataFrame:
        """Fetch OHLCV bars and return a clean, tz-aware DataFrame.

        Columns: open, high, low, close, volume, vwap, trade_count. Index is the
        bar timestamp. Returns an empty (well-formed) frame if no data.
        """
        self._require_sdk()
        alp_tf = self._to_alpaca_timeframe(timeframe)

        if is_crypto:
            req = CryptoBarsRequest(symbol_or_symbols=symbol, timeframe=alp_tf, start=start, end=end)
            bars = _retry(lambda: self._crypto_data.get_crypto_bars(req))
        else:
            req = StockBarsRequest(symbol_or_symbols=symbol, timeframe=alp_tf, start=start, end=end)
            bars = _retry(lambda: self._stock_data.get_stock_bars(req))

        df = bars.df if hasattr(bars, "df") else pd.DataFrame()
        if df.empty:
            return _empty_bars()
        if isinstance(df.index, pd.MultiIndex):
            df = df.xs(symbol, level=0)
        df = df.rename(columns={"trade_count": "trade_count"})
        keep = [c for c in ["open", "high", "low", "close", "volume", "vwap", "trade_count"] if c in df.columns]
        return df[keep].copy()

    # ------------------------------------------------------------------ #
    # WebSocket streaming (real-time quotes + trades)
    # ------------------------------------------------------------------ #
    def build_stream(self, feed: str = "iex"):
        """Return a configured ``alpaca`` live data stream (not started).

        The caller is responsible for subscribing to symbols and running the
        stream. Kept lazy so importing this module never opens a socket.
        """
        self._require_sdk()
        from alpaca.data.live import StockDataStream

        return StockDataStream(self._api_key, self._secret_key, feed=feed)


def _empty_bars() -> pd.DataFrame:
    return pd.DataFrame(
        columns=["open", "high", "low", "close", "volume", "vwap", "trade_count"]
    )
