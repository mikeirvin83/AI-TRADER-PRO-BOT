"""Dynamic watchlist / asset universe management."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set

from config.constants import (
    DEFAULT_CRYPTO_UNIVERSE,
    DEFAULT_EQUITY_UNIVERSE,
    DEFAULT_FUTURES_UNIVERSE,
    AssetClass,
)
from config.logging_config import get_logger

log = get_logger(__name__)


@dataclass
class AssetUniverse:
    """Holds the active tradable universe, grouped by asset class."""

    equities: Set[str] = field(default_factory=lambda: set(DEFAULT_EQUITY_UNIVERSE))
    crypto: Set[str] = field(default_factory=lambda: set(DEFAULT_CRYPTO_UNIVERSE))
    futures: Set[str] = field(default_factory=lambda: set(DEFAULT_FUTURES_UNIVERSE))

    def all_symbols(self) -> List[str]:
        return sorted(self.equities | self.crypto | self.futures)

    def add(self, symbol: str, asset_class: AssetClass) -> None:
        bucket = self._bucket(asset_class)
        bucket.add(symbol)
        log.info("universe_add", symbol=symbol, asset_class=asset_class.value)

    def remove(self, symbol: str) -> None:
        for bucket in (self.equities, self.crypto, self.futures):
            bucket.discard(symbol)

    def asset_class_of(self, symbol: str) -> AssetClass:
        if symbol in self.crypto:
            return AssetClass.CRYPTO
        if symbol in self.futures:
            return AssetClass.FUTURE
        return AssetClass.EQUITY

    def _bucket(self, asset_class: AssetClass) -> Set[str]:
        return {
            AssetClass.CRYPTO: self.crypto,
            AssetClass.FUTURE: self.futures,
        }.get(asset_class, self.equities)

    def as_dict(self) -> Dict[str, List[str]]:
        return {
            "equities": sorted(self.equities),
            "crypto": sorted(self.crypto),
            "futures": sorted(self.futures),
        }
