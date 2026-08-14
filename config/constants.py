"""System-wide constants and enumerations.

Single source of truth for asset classes, timeframes, market regimes, strategy
lifecycle states, order types, market sessions and futures contract specs.
"""
from __future__ import annotations

from datetime import time
from enum import Enum
from typing import Dict, NamedTuple

# --------------------------------------------------------------------------- #
# Market hours (US equities, Eastern Time). Crypto trades 24/7.
# --------------------------------------------------------------------------- #
NYSE_OPEN = time(9, 30)
NYSE_CLOSE = time(16, 0)
NYSE_PREMARKET_OPEN = time(4, 0)
NYSE_AFTERHOURS_CLOSE = time(20, 0)
MARKET_TIMEZONE = "America/New_York"


class AssetClass(str, Enum):
    EQUITY = "EQUITY"
    ETF = "ETF"
    CRYPTO = "CRYPTO"
    FUTURE = "FUTURE"
    OPTION = "OPTION"


class Timeframe(str, Enum):
    """Supported bar timeframes. Values map to Alpaca timeframe strings."""

    M1 = "1Min"
    M5 = "5Min"
    M15 = "15Min"
    M30 = "30Min"
    H1 = "1Hour"
    H4 = "4Hour"
    D1 = "1Day"
    W1 = "1Week"

    @property
    def seconds(self) -> int:
        return {
            "1Min": 60,
            "5Min": 300,
            "15Min": 900,
            "30Min": 1800,
            "1Hour": 3600,
            "4Hour": 14400,
            "1Day": 86400,
            "1Week": 604800,
        }[self.value]


class MarketRegime(str, Enum):
    """The 10 canonical market regime classifications."""

    STRONG_UPTREND = "STRONG_UPTREND"
    WEAK_UPTREND = "WEAK_UPTREND"
    STRONG_DOWNTREND = "STRONG_DOWNTREND"
    WEAK_DOWNTREND = "WEAK_DOWNTREND"
    RANGE_BOUND = "RANGE_BOUND"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"
    BREAKOUT = "BREAKOUT"
    REVERSAL = "REVERSAL"
    CHOPPY = "CHOPPY"


class StrategyStatus(str, Enum):
    ACTIVE = "ACTIVE"
    WATCH = "WATCH"
    DEGRADED = "DEGRADED"
    SUSPENDED = "SUSPENDED"
    RETIRED = "RETIRED"
    UNDER_RESEARCH = "UNDER_RESEARCH"


class HypothesisStatus(str, Enum):
    PROPOSED = "PROPOSED"
    TESTING = "TESTING"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    DEPLOYED = "DEPLOYED"
    ARCHIVED = "ARCHIVED"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class SignalDirection(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"


class MarketSession(str, Enum):
    PREMARKET = "PREMARKET"
    REGULAR = "REGULAR"
    AFTERHOURS = "AFTERHOURS"
    CLOSED = "CLOSED"


class DataQuality(str, Enum):
    CLEAN = "CLEAN"
    WARNING = "WARNING"
    CORRUPTED = "CORRUPTED"


# --------------------------------------------------------------------------- #
# Futures contract specifications (micro futures).
# tick_value = price move of one tick expressed in dollars.
# --------------------------------------------------------------------------- #
class FuturesSpec(NamedTuple):
    symbol: str
    name: str
    exchange: str
    tick_size: float          # minimum price increment
    tick_value: float         # $ value of one tick per contract
    contract_multiplier: float  # $ per full index point
    currency: str = "USD"


FUTURES_SPECS: Dict[str, FuturesSpec] = {
    # Micro E-mini S&P 500: $5 per point, tick 0.25 => $1.25/tick
    "MES": FuturesSpec("MES", "Micro E-mini S&P 500", "CME", 0.25, 1.25, 5.0),
    # Micro E-mini Nasdaq-100: $2 per point, tick 0.25 => $0.50/tick
    "MNQ": FuturesSpec("MNQ", "Micro E-mini Nasdaq-100", "CME", 0.25, 0.50, 2.0),
    # Micro E-mini Dow: $0.50 per point, tick 1.0 => $0.50/tick
    "MYM": FuturesSpec("MYM", "Micro E-mini Dow Jones", "CBOT", 1.0, 0.50, 0.50),
    # Micro E-mini Russell 2000: $5 per point, tick 0.10 => $0.50/tick
    "M2K": FuturesSpec("M2K", "Micro E-mini Russell 2000", "CME", 0.10, 0.50, 5.0),
}


# --------------------------------------------------------------------------- #
# Internal event bus topic names.
# --------------------------------------------------------------------------- #
class EventTopic(str, Enum):
    DATA_UPDATE = "DATA_UPDATE"
    SIGNAL_GENERATED = "SIGNAL_GENERATED"
    ORDER_PLACED = "ORDER_PLACED"
    ORDER_FILLED = "ORDER_FILLED"
    RISK_BREACH = "RISK_BREACH"
    REGIME_CHANGE = "REGIME_CHANGE"
    NEWS_EVENT = "NEWS_EVENT"
    MODE_CHANGE = "MODE_CHANGE"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    HEARTBEAT = "HEARTBEAT"


# Default asset universe seed (liquid, well-behaved instruments).
DEFAULT_EQUITY_UNIVERSE = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "AMZN", "META", "TSLA"]
DEFAULT_CRYPTO_UNIVERSE = ["BTC/USD", "ETH/USD"]
DEFAULT_FUTURES_UNIVERSE = ["MES", "MNQ", "MYM", "M2K"]

TRADING_DAYS_PER_YEAR = 252
