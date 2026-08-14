"""WebSocket stream lifecycle manager.

Owns subscription state and the async run loop for a live Alpaca data stream,
translating incoming ticks into internal ``DATA_UPDATE`` events on the event bus.
Designed so that the socket is only opened when :meth:`start` is called.
"""
from __future__ import annotations

import asyncio
from typing import Callable, Dict, List, Optional

from config.constants import EventTopic
from config.logging_config import get_logger
from core.event_bus import Event, get_event_bus
from market_data.alpaca_client import AlpacaClient

log = get_logger(__name__)


class StreamManager:
    def __init__(self, client: Optional[AlpacaClient] = None) -> None:
        self.client = client or AlpacaClient()
        self._bus = get_event_bus()
        self._symbols: List[str] = []
        self._stream = None
        self._task: Optional[asyncio.Task] = None
        self._running = False

    def subscribe_symbols(self, symbols: List[str]) -> None:
        for s in symbols:
            if s not in self._symbols:
                self._symbols.append(s)

    async def _on_bar(self, bar) -> None:
        await self._bus.publish(
            Event(EventTopic.DATA_UPDATE, payload={"bar": getattr(bar, "__dict__", {})},
                  source="stream_manager")
        )

    async def start(self) -> None:
        """Start the live stream. No-op if SDK/credentials unavailable."""
        if not self.client.sdk_available:
            log.warning("stream_not_started_no_sdk")
            return
        if self._running:
            return
        self._stream = self.client.build_stream()
        for s in self._symbols:
            self._stream.subscribe_bars(self._on_bar, s)
        self._running = True
        log.info("stream_starting", symbols=self._symbols)
        # alpaca-py stream.run() is blocking; run in executor-friendly task.
        self._task = asyncio.create_task(asyncio.to_thread(self._stream.run))

    async def stop(self) -> None:
        self._running = False
        if self._stream is not None:
            try:
                await self._stream.stop_ws()
            except Exception:  # noqa: BLE001
                pass
        if self._task:
            self._task.cancel()
        log.info("stream_stopped")

    @property
    def is_running(self) -> bool:
        return self._running
