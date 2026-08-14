"""Lightweight async publish/subscribe event bus for internal events.

Decouples producers (data feed, signal generator, risk engine) from consumers
(agents, loggers, alerters). Handlers may be sync or async callables.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Union

from config.constants import EventTopic
from config.logging_config import get_logger

log = get_logger(__name__)

Handler = Callable[["Event"], Union[None, Awaitable[None]]]


@dataclass
class Event:
    """An event flowing through the bus."""

    topic: EventTopic
    payload: Dict[str, Any] = field(default_factory=dict)
    source: str = "unknown"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class EventBus:
    """In-process async pub/sub bus."""

    def __init__(self) -> None:
        self._subscribers: Dict[EventTopic, List[Handler]] = defaultdict(list)
        self._lock = asyncio.Lock()

    def subscribe(self, topic: EventTopic, handler: Handler) -> None:
        """Register a handler for a topic."""
        self._subscribers[topic].append(handler)
        log.debug("event_subscribed", topic=topic.value, handler=getattr(handler, "__name__", str(handler)))

    def unsubscribe(self, topic: EventTopic, handler: Handler) -> None:
        if handler in self._subscribers.get(topic, []):
            self._subscribers[topic].remove(handler)

    async def publish(self, event: Event) -> None:
        """Publish an event, dispatching to all subscribers concurrently."""
        handlers = list(self._subscribers.get(event.topic, []))
        if not handlers:
            return
        coros = []
        for handler in handlers:
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    coros.append(result)
            except Exception:  # noqa: BLE001 - never let one handler kill the bus
                log.exception("event_handler_error_sync", topic=event.topic.value)
        if coros:
            results = await asyncio.gather(*coros, return_exceptions=True)
            for r in results:
                if isinstance(r, Exception):
                    log.error("event_handler_error_async", topic=event.topic.value, error=str(r))

    def publish_nowait(self, event: Event) -> None:
        """Fire-and-forget publish from sync context (schedules on running loop)."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.publish(event))
        except RuntimeError:
            # No running loop — run synchronously.
            asyncio.run(self.publish(event))


# Process-wide default bus.
_bus = EventBus()


def get_event_bus() -> EventBus:
    return _bus
