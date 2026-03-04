"""
Thread-safe reads and writes to feeds.json.
"""
import json
import threading
from pathlib import Path

from config import FEEDS_FILE

_lock = threading.Lock()


def read_feeds(path: Path | None = None) -> list[dict]:
    p = path or FEEDS_FILE
    with _lock:
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("feeds", [])
        except FileNotFoundError:
            return []


def _write_feeds(feeds: list[dict], path: Path | None = None) -> None:
    """Internal: write feeds list to disk (caller must hold _lock)."""
    p = path or FEEDS_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"feeds": feeds}, f, ensure_ascii=False, indent=2)


def add_feed(name: str, url: str, path: Path | None = None) -> dict:
    """
    Add a feed. Returns {'success': True} or {'success': False, 'error': ...}.
    """
    with _lock:
        p = path or FEEDS_FILE
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            data = {"feeds": []}

        feeds = data.get("feeds", [])
        # Dedup by name or URL
        for existing in feeds:
            if existing.get("name") == name:
                return {"success": False, "error": f"Feed name '{name}' already exists"}
            if existing.get("url") == url:
                return {"success": False, "error": f"URL already subscribed as '{existing.get('name')}'"}

        feeds.append({"name": name, "url": url})
        _write_feeds(feeds, p)
        return {"success": True}


def remove_feed(name: str, path: Path | None = None) -> dict:
    """
    Remove a feed by exact name match.
    Returns {'success': True, 'removed': True/False}.
    """
    with _lock:
        p = path or FEEDS_FILE
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            return {"success": True, "removed": False}

        feeds = data.get("feeds", [])
        new_feeds = [f for f in feeds if f.get("name") != name]
        removed = len(new_feeds) < len(feeds)
        _write_feeds(new_feeds, p)
        return {"success": True, "removed": removed}
