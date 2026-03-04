"""
APScheduler-based background scheduler for periodic feed refresh + briefing.
"""
from datetime import datetime, timezone
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

import cache
import fetcher
import briefing as briefing_mod

_scheduler = BackgroundScheduler(timezone="UTC")
_JOB_ID = "auto_refresh"

_state: dict[str, Any] = {
    "enabled": False,
    "interval_minutes": 30,
    "last_run": None,
}


def _refresh_task() -> None:
    """Fetch all feeds, generate briefing, store in cache."""
    _state["last_run"] = datetime.now(timezone.utc).isoformat()
    try:
        articles = fetcher.fetch_all()
        cache.set_articles(articles)
        text = briefing_mod.generate_briefing_sync(articles)
        cache.set_briefing(text)
    except Exception as e:
        print(f"[scheduler] refresh error: {e}")


def start() -> None:
    """Start the APScheduler (called once at app startup)."""
    if not _scheduler.running:
        _scheduler.start()


def shutdown() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)


def set_interval(minutes: int) -> None:
    """Set auto-refresh interval. minutes=0 disables the job."""
    # Remove existing job if any
    if _scheduler.get_job(_JOB_ID):
        _scheduler.remove_job(_JOB_ID)

    if minutes <= 0:
        _state["enabled"] = False
        _state["interval_minutes"] = 0
        return

    _state["enabled"] = True
    _state["interval_minutes"] = minutes
    _scheduler.add_job(
        _refresh_task,
        trigger=IntervalTrigger(minutes=minutes),
        id=_JOB_ID,
        replace_existing=True,
    )


def get_status() -> dict:
    """Return current scheduler state."""
    job = _scheduler.get_job(_JOB_ID)
    next_run = None
    if job and job.next_run_time:
        next_run = job.next_run_time.isoformat()

    return {
        "enabled": _state["enabled"],
        "interval_minutes": _state["interval_minutes"],
        "next_run": next_run,
        "last_run": _state["last_run"],
    }
