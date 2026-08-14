"""Master system state — trading mode + kill switch.

This is the single authority for whether trading is allowed and in what mode.
It is a thread-safe singleton. The risk engine and any critical fault handler
may call :meth:`engage_emergency_stop` to instantly halt all trading.

Mode transition rules (STRICT — enforced, cannot be bypassed):

    DISABLED  -> RESEARCH, BACKTEST, PAPER
    RESEARCH  <-> BACKTEST <-> PAPER
    PAPER     -> SHADOW              (only forward promotion path)
    SHADOW    -> LIVE                (only forward promotion path)
    LIVE      -> SHADOW, PAPER, EMERGENCY_STOP
    *any*     -> EMERGENCY_STOP      (always allowed)
    EMERGENCY_STOP -> DISABLED       (manual reset only)

You can NEVER skip a promotion stage (e.g. PAPER -> LIVE directly is illegal),
and the system can never self-promote to LIVE without going through SHADOW.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from config.logging_config import get_logger
from config.settings import TradingMode, get_settings

log = get_logger(__name__)


# Allowed forward/lateral transitions. EMERGENCY_STOP is always reachable and
# handled separately so it is intentionally not listed as a target here.
_ALLOWED_TRANSITIONS: dict[TradingMode, set[TradingMode]] = {
    TradingMode.DISABLED: {TradingMode.RESEARCH, TradingMode.BACKTEST, TradingMode.PAPER},
    TradingMode.RESEARCH: {TradingMode.BACKTEST, TradingMode.PAPER, TradingMode.DISABLED},
    TradingMode.BACKTEST: {TradingMode.RESEARCH, TradingMode.PAPER, TradingMode.DISABLED},
    TradingMode.PAPER: {TradingMode.RESEARCH, TradingMode.BACKTEST, TradingMode.SHADOW, TradingMode.DISABLED},
    TradingMode.SHADOW: {TradingMode.PAPER, TradingMode.LIVE, TradingMode.DISABLED},
    TradingMode.LIVE: {TradingMode.SHADOW, TradingMode.PAPER},
    TradingMode.EMERGENCY_STOP: {TradingMode.DISABLED},
}

# Modes in which real or simulated orders may be routed.
_TRADING_MODES = {TradingMode.PAPER, TradingMode.SHADOW, TradingMode.LIVE}


@dataclass(frozen=True)
class StateTransition:
    """Immutable audit record of a single mode transition."""

    from_mode: TradingMode
    to_mode: TradingMode
    reason: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    actor: str = "system"


class IllegalTransitionError(RuntimeError):
    """Raised when a requested mode transition violates the promotion rules."""


class SystemState:
    """Thread-safe singleton holding the master trading mode & kill switch."""

    _instance: Optional["SystemState"] = None
    _singleton_lock = threading.Lock()

    def __new__(cls) -> "SystemState":
        with cls._singleton_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_state()
            return cls._instance

    def _init_state(self) -> None:
        self._lock = threading.RLock()
        self._mode: TradingMode = get_settings().TRADING_MODE
        self._emergency: bool = False
        self._emergency_reason: Optional[str] = None
        self._history: List[StateTransition] = [
            StateTransition(self._mode, self._mode, "initial", actor="boot")
        ]

    # ------------------------------------------------------------------ #
    # Read helpers
    # ------------------------------------------------------------------ #
    def get_mode(self) -> TradingMode:
        with self._lock:
            return self._mode

    def is_trading_allowed(self) -> bool:
        """True only when not in emergency stop and in a trading-capable mode."""
        with self._lock:
            return not self._emergency and self._mode in _TRADING_MODES

    def is_emergency_stopped(self) -> bool:
        with self._lock:
            return self._emergency

    def get_history(self) -> List[StateTransition]:
        with self._lock:
            return list(self._history)

    # ------------------------------------------------------------------ #
    # Transitions
    # ------------------------------------------------------------------ #
    def transition_to(
        self, new_mode: TradingMode, reason: str, actor: str = "system"
    ) -> TradingMode:
        """Attempt a validated mode transition.

        Raises :class:`IllegalTransitionError` if the transition is not allowed.
        """
        with self._lock:
            if self._emergency and new_mode != TradingMode.DISABLED:
                raise IllegalTransitionError(
                    "System is in EMERGENCY_STOP; only manual reset to DISABLED is allowed."
                )

            if new_mode == TradingMode.EMERGENCY_STOP:
                # Use the dedicated method so the emergency flag is set.
                return self.engage_emergency_stop(reason, actor=actor)

            if new_mode == self._mode:
                return self._mode

            allowed = _ALLOWED_TRANSITIONS.get(self._mode, set())
            if new_mode not in allowed:
                raise IllegalTransitionError(
                    f"Illegal transition {self._mode.value} -> {new_mode.value}. "
                    f"Allowed: {sorted(m.value for m in allowed)}"
                )

            prev = self._mode
            self._mode = new_mode
            self._history.append(StateTransition(prev, new_mode, reason, actor=actor))
            log.info(
                "mode_transition",
                from_mode=prev.value,
                to_mode=new_mode.value,
                reason=reason,
                actor=actor,
            )
            return self._mode

    def engage_emergency_stop(self, reason: str, actor: str = "system") -> TradingMode:
        """Immediately halt all trading. Always succeeds."""
        with self._lock:
            prev = self._mode
            self._emergency = True
            self._emergency_reason = reason
            self._mode = TradingMode.EMERGENCY_STOP
            self._history.append(
                StateTransition(prev, TradingMode.EMERGENCY_STOP, reason, actor=actor)
            )
            log.error("emergency_stop_engaged", from_mode=prev.value, reason=reason, actor=actor)
            return self._mode

    def reset_emergency_stop(self, reason: str, actor: str = "operator") -> TradingMode:
        """Manual reset from EMERGENCY_STOP back to DISABLED. Human action only."""
        with self._lock:
            if not self._emergency:
                return self._mode
            self._emergency = False
            self._emergency_reason = None
            prev = self._mode
            self._mode = TradingMode.DISABLED
            self._history.append(
                StateTransition(prev, TradingMode.DISABLED, f"reset: {reason}", actor=actor)
            )
            log.warning("emergency_stop_reset", reason=reason, actor=actor)
            return self._mode

    @property
    def emergency_reason(self) -> Optional[str]:
        with self._lock:
            return self._emergency_reason


def get_system_state() -> SystemState:
    """Accessor for the SystemState singleton."""
    return SystemState()
