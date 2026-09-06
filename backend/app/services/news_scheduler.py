"""
Scheduled News Ingestion Service for TruthTrace.

Uses the production-grade IngestionOrchestrator from ingest_pipeline.py.
Tracks last-run statistics and exposes them via get_scheduler_status().
"""

import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from apscheduler.schedulers.background import BackgroundScheduler

# Ensure backend root is on sys.path so ingest_pipeline can be imported
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# ─── Globals ──────────────────────────────────────────────────────────────────
scheduler = BackgroundScheduler()
_stats_lock = threading.Lock()
_last_run_stats: Optional[Dict[str, Any]] = None
_interval_hours: int = 6


# ─── Core Job ─────────────────────────────────────────────────────────────────

def _run_ingestion_cycle():
    """Execute one ingestion cycle via IngestionOrchestrator and store stats."""
    global _last_run_stats

    started_at = datetime.now()
    print(f"\n[{started_at.strftime('%Y-%m-%d %H:%M:%S')}] Scheduler: starting news ingestion cycle...")

    try:
        from ingest_pipeline import IngestionOrchestrator

        orchestrator = IngestionOrchestrator()
        try:
            summary = orchestrator.run_cycle(sources=["rss", "factcheck"], limit_per_cycle=100)
        finally:
            orchestrator.close()

        summary["started_at"] = started_at.isoformat()
        summary["finished_at"] = datetime.now().isoformat()
        summary["status"] = "ok"

    except Exception as exc:
        print(f"[Scheduler] Ingestion cycle error: {exc}")
        summary = {
            "started_at": started_at.isoformat(),
            "finished_at": datetime.now().isoformat(),
            "status": "error",
            "error": str(exc),
        }

    with _stats_lock:
        _last_run_stats = summary

    print(f"[Scheduler] Cycle complete — {summary.get('fresh_indexed_docs', 0)} docs indexed.")


# ─── Control Functions ────────────────────────────────────────────────────────

def start_news_scheduler(interval_hours: int = 6) -> None:
    """Start the background scheduler. Safe to call multiple times."""
    global _interval_hours
    _interval_hours = interval_hours

    if scheduler.running:
        return

    scheduler.add_job(
        _run_ingestion_cycle,
        "interval",
        hours=interval_hours,
        id="news_ingestion_job",
        name="TruthTrace — Scheduled News Ingestion",
        replace_existing=True,
    )
    scheduler.start()
    print(f"✓ News ingestion scheduler started (every {interval_hours}h)")


def stop_news_scheduler() -> None:
    """Gracefully stop the background scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        print("✓ News ingestion scheduler stopped")


def trigger_now() -> None:
    """Immediately fire one ingestion cycle without waiting for the next interval."""
    t = threading.Thread(target=_run_ingestion_cycle, daemon=True, name="news-ingest-immediate")
    t.start()


def get_scheduler_status() -> Dict[str, Any]:
    """Return current scheduler state plus last-run statistics."""
    jobs = scheduler.get_jobs()
    next_run: Optional[str] = None
    if jobs:
        nrt = jobs[0].next_run_time
        next_run = nrt.isoformat() if nrt else None

    with _stats_lock:
        last = _last_run_stats.copy() if _last_run_stats else None

    return {
        "running": scheduler.running,
        "interval_hours": _interval_hours,
        "job_count": len(jobs),
        "next_run": next_run,
        "last_run": last,
    }
