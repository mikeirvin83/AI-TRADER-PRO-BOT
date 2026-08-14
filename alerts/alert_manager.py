"""Alerting subsystem.

Provides a small, dependency-light alert pipeline that fans a structured
:class:`Alert` out to one or more :class:`AlertChannel` implementations.

Design goals
------------
* **No hard external dependency.** The default channel simply logs via
  ``structlog`` so the platform works out-of-the-box. Slack/email/webhook
  channels are optional and degrade gracefully when their config or
  network dependency is unavailable — they never raise into the caller.
* **Severity aware.** Channels can filter by a minimum severity.
* **Risk-first.** ``CRITICAL`` alerts (e.g. kill-switch engaged, circuit
  breaker tripped) are always delivered to every registered channel.
"""
from __future__ import annotations

import enum
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol

import httpx

from config.logging_config import get_logger

logger = get_logger(__name__)


class AlertSeverity(str, enum.Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    @property
    def rank(self) -> int:
        return {"INFO": 0, "WARNING": 1, "ERROR": 2, "CRITICAL": 3}[self.value]


@dataclass(slots=True)
class Alert:
    """A single structured alert event."""

    title: str
    message: str
    severity: AlertSeverity = AlertSeverity.INFO
    source: str = "system"
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "message": self.message,
            "severity": self.severity.value,
            "source": self.source,
            "context": self.context,
            "created_at": self.created_at.isoformat(),
        }


class AlertChannel(Protocol):
    """Protocol every delivery channel must satisfy."""

    name: str
    min_severity: AlertSeverity

    def send(self, alert: Alert) -> bool:  # pragma: no cover - protocol
        ...


class LogChannel:
    """Default channel — emits the alert through the structured logger."""

    def __init__(self, min_severity: AlertSeverity = AlertSeverity.INFO) -> None:
        self.name = "log"
        self.min_severity = min_severity

    def send(self, alert: Alert) -> bool:
        log = logger.bind(channel=self.name, source=alert.source, **alert.context)
        level = {
            AlertSeverity.INFO: log.info,
            AlertSeverity.WARNING: log.warning,
            AlertSeverity.ERROR: log.error,
            AlertSeverity.CRITICAL: log.critical,
        }[alert.severity]
        level("alert", title=alert.title, message=alert.message,
              severity=alert.severity.value)
        return True


class WebhookChannel:
    """Generic HTTP webhook channel (Slack-compatible payload).

    Fails soft: any network/config error is logged and swallowed so alerting
    never takes down the trading loop.
    """

    def __init__(
        self,
        url: Optional[str],
        min_severity: AlertSeverity = AlertSeverity.WARNING,
        timeout: float = 5.0,
        name: str = "webhook",
    ) -> None:
        self.name = name
        self.url = url
        self.min_severity = min_severity
        self.timeout = timeout

    def send(self, alert: Alert) -> bool:
        if not self.url:
            logger.debug("alert.webhook.skipped_no_url", channel=self.name)
            return False
        payload = {
            "text": f"[{alert.severity.value}] {alert.title}\n{alert.message}",
            "attachments": [{"text": json.dumps(alert.to_dict(), default=str)}],
        }
        try:
            resp = httpx.post(self.url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            return True
        except Exception as exc:  # noqa: BLE001 - fail soft
            logger.warning("alert.webhook.failed", channel=self.name, error=str(exc))
            return False


class AlertManager:
    """Fans alerts out to all registered channels respecting severity floors."""

    def __init__(self, channels: Optional[List[AlertChannel]] = None) -> None:
        self._channels: List[AlertChannel] = list(channels) if channels else [LogChannel()]

    def register(self, channel: AlertChannel) -> None:
        self._channels.append(channel)

    @property
    def channels(self) -> List[AlertChannel]:
        return list(self._channels)

    def dispatch(self, alert: Alert) -> Dict[str, bool]:
        """Send an alert to every eligible channel; returns per-channel result."""
        results: Dict[str, bool] = {}
        for ch in self._channels:
            eligible = (
                alert.severity is AlertSeverity.CRITICAL
                or alert.severity.rank >= ch.min_severity.rank
            )
            if not eligible:
                continue
            try:
                results[ch.name] = bool(ch.send(alert))
            except Exception as exc:  # noqa: BLE001 - never propagate
                logger.error("alert.channel.error", channel=ch.name, error=str(exc))
                results[ch.name] = False
        return results

    # Convenience helpers -------------------------------------------------- #
    def info(self, title: str, message: str, **context: Any) -> Dict[str, bool]:
        return self.dispatch(Alert(title, message, AlertSeverity.INFO, context=context))

    def warning(self, title: str, message: str, **context: Any) -> Dict[str, bool]:
        return self.dispatch(Alert(title, message, AlertSeverity.WARNING, context=context))

    def error(self, title: str, message: str, **context: Any) -> Dict[str, bool]:
        return self.dispatch(Alert(title, message, AlertSeverity.ERROR, context=context))

    def critical(self, title: str, message: str, **context: Any) -> Dict[str, bool]:
        return self.dispatch(Alert(title, message, AlertSeverity.CRITICAL, context=context))


_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """Process-wide singleton accessor."""
    global _manager
    if _manager is None:
        _manager = AlertManager()
    return _manager
