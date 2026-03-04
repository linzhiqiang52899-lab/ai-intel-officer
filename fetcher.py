"""
Bridge module that dynamically loads fetch-feeds.py from the rss-intel skill
and exposes validate_feed, fetch_single, and fetch_all.
"""
import importlib.util
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from config import SCRIPTS_DIR, FEEDS_FILE

# ── Dynamic load of fetch-feeds.py ──────────────────────────────────────────
_spec = importlib.util.spec_from_file_location(
    "fetch_feeds", SCRIPTS_DIR / "fetch-feeds.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

_fetch_and_parse = _mod.fetch_and_parse  # the core function


# ── Public API ───────────────────────────────────────────────────────────────

def validate_feed(url: str) -> dict:
    """Return validation result for a single feed URL."""
    result = _fetch_and_parse(url)
    if result["success"]:
        return {
            "valid": True,
            "url": url,
            "feed_title": result.get("feed_title", "") or url,
            "article_count": result.get("article_count", 0),
        }
    return {
        "valid": False,
        "url": url,
        "error": result.get("error", "Unknown error"),
    }


def fetch_single(url: str) -> dict:
    """Fetch and parse a single feed URL, return raw result dict."""
    return _fetch_and_parse(url)


def fetch_all(feeds_path: Path | None = None) -> dict:
    """
    Concurrent fetch of all feeds in feeds.json.
    Returns {'success': True, 'results': [...]} matching the CLI format.
    """
    path = feeds_path or FEEDS_FILE
    try:
        with open(path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        return {"success": False, "error": str(e), "results": []}

    feeds = config.get("feeds", [])
    if not feeds:
        return {"success": True, "results": [], "message": "No feeds configured"}

    results: list[dict] = [None] * len(feeds)

    def _fetch_one(idx: int, feed: dict) -> tuple[int, dict]:
        url = feed.get("url", "")
        name = feed.get("name", "")
        if not url:
            return idx, {"success": False, "url": "", "error": "No URL", "articles": []}
        r = _fetch_and_parse(url)
        if name:
            r["configured_name"] = name
        return idx, r

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_fetch_one, i, feed): i for i, feed in enumerate(feeds)}
        for future in as_completed(futures):
            idx, r = future.result()
            results[idx] = r

    return {"success": True, "results": results}
