#!/usr/bin/env python3
"""Entrypoint for the paper-trading loop.

SAFETY: this script refuses to run unless the configured trading mode is a
non-live mode (PAPER by default). It never sets or reads a live-trading
authorization flag. Promotion to live capital is a separate, human-gated
process documented in RUNBOOK.md.

Usage:
    python run_paper.py
    python run_paper.py --symbols SPY,QQQ,AAPL --interval 60 --cash 100000
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run the paper-trading loop.")
    p.add_argument(
        "--symbols",
        default=None,
        help="Comma separated symbol list (default: platform watchlist).",
    )
    p.add_argument(
        "--cash",
        type=float,
        default=100_000.0,
        help="Starting simulated cash (default: 100000).",
    )
    p.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Seconds between scans (default: 60).",
    )
    p.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level (default: INFO).",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    log = logging.getLogger("run_paper")

    from config.settings import get_settings

    settings = get_settings()
    mode = str(getattr(settings, "TRADING_MODE", "PAPER")).upper()
    if mode == "LIVE":
        log.error(
            "TRADING_MODE=LIVE is not permitted by this entrypoint. "
            "Use the documented promotion process instead."
        )
        return 2
    log.info("Trading mode: %s (no live capital at risk)", mode)

    from orchestration.paper_trading_loop import PaperTradingLoop

    symbols = None
    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    loop = PaperTradingLoop(
        symbols=symbols,
        starting_cash=args.cash,
        scan_interval_seconds=args.interval,
    )

    async def _run() -> None:
        running = asyncio.get_running_loop()
        for sig_name in ("SIGINT", "SIGTERM"):
            sig = getattr(signal, sig_name, None)
            if sig is None:
                continue
            try:
                running.add_signal_handler(
                    sig, lambda: asyncio.ensure_future(loop.stop())
                )
            except (NotImplementedError, RuntimeError):
                # Windows event loops do not support add_signal_handler.
                pass
        await loop.run()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        log.info("Interrupted - shutting down.")
    log.info("Paper trading loop stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
