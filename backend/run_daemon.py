#!/usr/bin/env python3
"""
TruthTrace Production Ingestion Daemon

A production-ready background process for continuous news ingestion.
Designed for deployment via systemd, Docker, or cron.

Features:
  - Runs ingest_pipeline.IngestionOrchestrator on a configurable interval
  - Handles SIGTERM and SIGINT for graceful shutdown
  - Logs structured JSON lines to stdout (and optionally a log file)
  - Emits a heartbeat line every cycle for monitoring

Usage:
  python run_daemon.py
  python run_daemon.py --interval 600 --sources rss,factcheck --limit 200
  python run_daemon.py --interval 3600 --log-file /var/log/truthtrace.log

Docker / systemd example:
  CMD ["python", "run_daemon.py", "--interval", "300", "--sources", "rss,factcheck"]
"""

import sys
import os
import json
import time
import signal
import logging
import argparse
from datetime import datetime, timezone
from pathlib import Path

# ── Bootstrap path ─────────────────────────────────────────────────────────────
_BACKEND = Path(__file__).resolve().parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


# ── Structured JSON logger ─────────────────────────────────────────────────────

class JsonLineFormatter(logging.Formatter):
    """Emits each log record as a single JSON line for log aggregators."""
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "msg": record.getMessage(),
        })


def build_logger(log_file: str | None = None) -> logging.Logger:
    logger = logging.getLogger("truthtrace.daemon")
    logger.setLevel(logging.INFO)

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    for h in handlers:
        h.setFormatter(JsonLineFormatter())
        logger.addHandler(h)

    return logger


# ── Daemon ─────────────────────────────────────────────────────────────────────

class Daemon:
    def __init__(self, sources: list, interval: int, limit: int, dry_run: bool, logger: logging.Logger):
        self.sources = sources
        self.interval = interval
        self.limit = limit
        self.dry_run = dry_run
        self.logger = logger
        self._running = True
        self._cycle = 0

        # Register shutdown signals
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        self.logger.info(f"Received signal {signum}. Shutting down gracefully…")
        self._running = False

    def run(self):
        from ingest_pipeline import IngestionOrchestrator

        self.logger.info(json.dumps({
            "event": "daemon_start",
            "sources": self.sources,
            "interval_sec": self.interval,
            "limit_per_cycle": self.limit,
            "dry_run": self.dry_run,
        }))

        orchestrator = IngestionOrchestrator(dry_run=self.dry_run)

        try:
            while self._running:
                self._cycle += 1
                started = time.time()

                self.logger.info(json.dumps({
                    "event": "cycle_start",
                    "cycle": self._cycle,
                }))

                try:
                    summary = orchestrator.run_cycle(
                        sources=self.sources,
                        limit_per_cycle=self.limit,
                    )
                    elapsed = round(time.time() - started, 2)
                    self.logger.info(json.dumps({
                        "event": "cycle_complete",
                        "cycle": self._cycle,
                        "elapsed_sec": elapsed,
                        **{k: v for k, v in summary.items() if k != "elapsed_sec"},
                    }))

                except Exception as exc:
                    self.logger.error(json.dumps({
                        "event": "cycle_error",
                        "cycle": self._cycle,
                        "error": str(exc),
                    }))

                # Sleep in small increments to allow fast shutdown on SIGTERM
                if self._running:
                    deadline = time.time() + self.interval
                    while self._running and time.time() < deadline:
                        time.sleep(min(5, deadline - time.time()))

        finally:
            orchestrator.close()
            self.logger.info(json.dumps({"event": "daemon_stopped", "cycles_run": self._cycle}))


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="TruthTrace Production Ingestion Daemon",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--sources", default="rss,factcheck",
                        help="Comma-separated sources: rss, factcheck, newsapi")
    parser.add_argument("--interval", type=int, default=300,
                        help="Seconds between ingestion cycles")
    parser.add_argument("--limit", type=int, default=100,
                        help="Max fresh documents per cycle")
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch and deduplicate without writing to vector store")
    parser.add_argument("--log-file", default=None,
                        help="Optional path to write structured JSON logs")
    args = parser.parse_args()

    sources = [s.strip().lower() for s in args.sources.split(",") if s.strip()]
    logger = build_logger(args.log_file)

    daemon = Daemon(
        sources=sources,
        interval=args.interval,
        limit=args.limit,
        dry_run=args.dry_run,
        logger=logger,
    )
    daemon.run()


if __name__ == "__main__":
    main()
