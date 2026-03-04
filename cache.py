"""
In-memory cache with file persistence.
Stores:
  - articles: result of the last fetch_all call
  - briefing: text of the last generated briefing
"""
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from config import CACHE_FILE

_lock = threading.Lock()

_store: dict = {
    "articles": None,        # raw fetch_all result
    "briefing": None,        # markdown string
    "articles_at": None,     # ISO timestamp
    "briefing_at": None,     # ISO timestamp
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _persist() -> None:
    """Write current store to disk (caller holds _lock)."""
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_store, f, ensure_ascii=False)
    except Exception:
        pass  # Non-fatal


def load_from_disk() -> None:
    """Called once at startup to restore cache from disk."""
    global _store
    with _lock:
        if not CACHE_FILE.exists():
            return
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            _store.update(data)
        except Exception:
            pass


def get_articles() -> dict | None:
    with _lock:
        return _store.get("articles")


def set_articles(data: dict) -> None:
    with _lock:
        _store["articles"] = data
        _store["articles_at"] = _now_iso()
        _persist()


def get_briefing() -> str | None:
    with _lock:
        return _store.get("briefing")


def get_briefing_at() -> str | None:
    with _lock:
        return _store.get("briefing_at")


def set_briefing(text: str) -> None:
    with _lock:
        _store["briefing"] = text
        _store["briefing_at"] = _now_iso()
        _persist()


def get_articles_at() -> str | None:
    with _lock:
        return _store.get("articles_at")
