"""Application settings.

Centralised, type-safe configuration for the Autonomous Adaptive Trading
Intelligence Platform. Everything is loaded from environment variables (12-factor
style) with sane, *safe* defaults. Secrets are NEVER hardcoded.

Credential resolution order for Alpaca:
    1. Environment variables (ALPACA_API_KEY / ALPACA_SECRET_KEY / ...)
    2. Fallback to the local secrets file written by the platform connector:
       /home/ubuntu/.config/abacusai_auth_secrets.json

The secrets file is expected to look like::

    {
      "alpaca": {
        "secrets": {
          "api_key":    {"value": "..."},
          "secret_key": {"value": "..."},
          "base_url":   {"value": "https://paper-api.alpaca.markets"}
        }
      }
    }

Both the service name ("Alpaca"/"alpaca"/"ALPACA") and the secret keys
("API_KEY"/"api_key" ...) are resolved case-insensitively so the loader is
robust across connector naming conventions.
"""
from __future__ import annotations

import json
import os
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SECRETS_FILE = Path("/home/ubuntu/.config/abacusai_auth_secrets.json")


class TradingMode(str, Enum):
    """Master operating mode. The system is *never* LIVE by default."""

    DISABLED = "DISABLED"
    RESEARCH = "RESEARCH"
    BACKTEST = "BACKTEST"
    PAPER = "PAPER"
    SHADOW = "SHADOW"
    LIVE = "LIVE"
    EMERGENCY_STOP = "EMERGENCY_STOP"


def _load_secret_service(service_names: tuple[str, ...]) -> Dict[str, str]:
    """Load a service block from the connector secrets file, case-insensitively.

    Returns a flat mapping of lower-cased secret-name -> value. Never raises;
    returns an empty dict when the file or service is missing.
    """
    if not SECRETS_FILE.exists():
        return {}
    try:
        data = json.loads(SECRETS_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}

    # Case-insensitive service lookup.
    block: Optional[Dict[str, Any]] = None
    lowered = {k.lower(): v for k, v in data.items()}
    for name in service_names:
        if name.lower() in lowered:
            block = lowered[name.lower()]
            break
    if not block:
        return {}

    secrets = block.get("secrets", {})
    out: Dict[str, str] = {}
    for key, val in secrets.items():
        if isinstance(val, dict) and "value" in val:
            out[key.lower()] = val["value"]
        elif isinstance(val, str):
            out[key.lower()] = val
    return out


class Settings(BaseSettings):
    """Typed application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------ #
    # Environment / meta
    # ------------------------------------------------------------------ #
    ENV: str = Field(default="development")
    DEBUG: bool = Field(default=False)
    APP_NAME: str = Field(default="autonomous-trading-platform")

    # ------------------------------------------------------------------ #
    # Alpaca credentials (resolved lazily, env first then secrets file)
    # ------------------------------------------------------------------ #
    ALPACA_API_KEY: Optional[str] = Field(default=None)
    ALPACA_SECRET_KEY: Optional[str] = Field(default=None)
    ALPACA_BASE_URL: str = Field(default="https://paper-api.alpaca.markets")
    ALPACA_DATA_URL: str = Field(default="https://data.alpaca.markets")
    # Market data feed for stock bars. "iex" works on every plan (including
    # free); "sip" requires a paid Alpaca data subscription.
    STOCK_DATA_FEED: str = Field(default="iex")

    # ------------------------------------------------------------------ #
    # Infrastructure
    # ------------------------------------------------------------------ #
    DATABASE_URL: str = Field(
        default="postgresql+psycopg2://trader:trader@localhost:5432/trading_platform"
    )
    REDIS_URL: str = Field(default="redis://localhost:6379/0")

    # ------------------------------------------------------------------ #
    # Trading mode — DEFAULTS TO PAPER. Never LIVE.
    # ------------------------------------------------------------------ #
    TRADING_MODE: TradingMode = Field(default=TradingMode.PAPER)

    # ------------------------------------------------------------------ #
    # Risk parameters (all percentages expressed as fractions of equity,
    # e.g. 0.01 == 1%). Every risk check reads from here — never hardcoded.
    # ------------------------------------------------------------------ #
    MAX_RISK_PER_TRADE_PCT: float = Field(default=0.01)      # 1% equity at risk / trade
    MAX_DAILY_LOSS_PCT: float = Field(default=0.03)          # 3% daily loss circuit breaker
    MAX_WEEKLY_LOSS_PCT: float = Field(default=0.06)         # 6% weekly loss circuit breaker
    MAX_PORTFOLIO_DRAWDOWN_PCT: float = Field(default=0.15)  # 15% peak-to-trough kill
    MAX_POSITION_SIZE_PCT: float = Field(default=0.20)       # 20% equity in one position
    MAX_LEVERAGE: float = Field(default=1.0)                 # cash only by default
    MAX_SIMULTANEOUS_TRADES: int = Field(default=5)
    MAX_CORRELATED_EXPOSURE_PCT: float = Field(default=0.30) # 30% equity in correlated cluster

    # ------------------------------------------------------------------ #
    # Signal quality thresholds (0-100 unified score)
    # ------------------------------------------------------------------ #
    SIGNAL_SCORE_MIN_QUALIFIED: int = Field(default=75)
    SIGNAL_SCORE_MIN_HIGH_QUALITY: int = Field(default=85)

    # ------------------------------------------------------------------ #
    # Promotion gates (paper -> shadow -> live)
    # ------------------------------------------------------------------ #
    MIN_PAPER_TRADES: int = Field(default=100)
    MIN_PAPER_DURATION_DAYS: int = Field(default=30)

    # ------------------------------------------------------------------ #
    # Backtest cost model defaults
    # ------------------------------------------------------------------ #
    DEFAULT_COMMISSION_PER_SHARE: float = Field(default=0.0)   # Alpaca stocks/crypto = $0
    DEFAULT_SLIPPAGE_BPS: float = Field(default=1.0)           # 1 bps default slippage
    RISK_FREE_RATE: float = Field(default=0.04)                # for Sharpe/Sortino

    # ------------------------------------------------------------------ #
    # Logging
    # ------------------------------------------------------------------ #
    LOG_LEVEL: str = Field(default="INFO")
    LOG_JSON: bool = Field(default=True)

    # ------------------------------------------------------------------ #
    # Validators
    # ------------------------------------------------------------------ #
    @field_validator("TRADING_MODE", mode="before")
    @classmethod
    def _coerce_mode(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.upper()
        return v

    def resolve_alpaca_credentials(self) -> Dict[str, str]:
        """Return resolved Alpaca creds, falling back to the secrets file.

        Does not mutate env; returns a dict with api_key/secret_key/base_url/data_url.
        """
        api_key = self.ALPACA_API_KEY or os.getenv("ALPACA_API_KEY")
        secret_key = self.ALPACA_SECRET_KEY or os.getenv("ALPACA_SECRET_KEY")
        base_url = self.ALPACA_BASE_URL
        data_url = self.ALPACA_DATA_URL

        if not api_key or not secret_key:
            secrets = _load_secret_service(("Alpaca", "alpaca", "ALPACA"))
            api_key = api_key or secrets.get("api_key")
            secret_key = secret_key or secrets.get("secret_key")
            if secrets.get("base_url"):
                base_url = secrets["base_url"]

        return {
            "api_key": api_key or "",
            "secret_key": secret_key or "",
            "base_url": base_url,
            "data_url": data_url,
        }

    @property
    def is_paper(self) -> bool:
        return "paper" in self.ALPACA_BASE_URL.lower()


@lru_cache
def get_settings() -> Settings:
    """Cached singleton accessor for application settings."""
    return Settings()


# Convenience module-level instance.
settings = get_settings()
