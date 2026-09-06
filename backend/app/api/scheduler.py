"""
Scheduler Control API — REST endpoints to manage the background news ingestion job.

Routes:
    GET  /api/scheduler/status   — current state + last-run stats
    POST /api/scheduler/start    — start scheduler (optional ?interval_hours=6)
    POST /api/scheduler/stop     — stop scheduler
    POST /api/scheduler/run-now  — trigger an immediate ingestion cycle (non-blocking)
"""

from typing import Any, Dict, Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services.news_scheduler import (
    start_news_scheduler,
    stop_news_scheduler,
    trigger_now,
    get_scheduler_status,
)

router = APIRouter(prefix="/scheduler", tags=["Scheduler"])


class SchedulerStatusResponse(BaseModel):
    running: bool
    interval_hours: int
    job_count: int
    next_run: Optional[str]
    last_run: Optional[Dict[str, Any]]


class MessageResponse(BaseModel):
    message: str


@router.get("/status", response_model=SchedulerStatusResponse)
async def scheduler_status() -> SchedulerStatusResponse:
    """
    Return the current scheduler state:
    - running: whether the background scheduler is active
    - interval_hours: configured ingestion frequency
    - next_run: ISO timestamp of the next scheduled run
    - last_run: summary stats from the most recent ingestion cycle
    """
    return SchedulerStatusResponse(**get_scheduler_status())


@router.post("/start", response_model=MessageResponse)
async def start_scheduler(
    interval_hours: int = Query(default=6, ge=1, le=168, description="Hours between ingestion runs")
) -> MessageResponse:
    """
    Start the background news ingestion scheduler.
    If already running, this is a no-op.
    """
    start_news_scheduler(interval_hours=interval_hours)
    return MessageResponse(message=f"Scheduler started — ingesting every {interval_hours} hour(s).")


@router.post("/stop", response_model=MessageResponse)
async def stop_scheduler() -> MessageResponse:
    """
    Stop the background news ingestion scheduler gracefully.
    Any in-progress ingestion cycle is allowed to finish.
    """
    stop_news_scheduler()
    return MessageResponse(message="Scheduler stopped.")


@router.post("/run-now", response_model=MessageResponse)
async def run_now() -> MessageResponse:
    """
    Trigger an immediate ingestion cycle in a background thread.
    Returns instantly — check /api/scheduler/status for results after a few seconds.
    """
    trigger_now()
    return MessageResponse(message="Ingestion cycle triggered. Check /api/scheduler/status for results.")
