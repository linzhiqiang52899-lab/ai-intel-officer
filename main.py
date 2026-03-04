"""
AI情报官 — FastAPI application entry point.
"""
import asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import cache
import feeds_manager
import fetcher
import briefing as briefing_mod
import scheduler
from config import STATIC_DIR, check_api_key

app = FastAPI(title="AI情报官", version="1.0.0")

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── Startup / Shutdown ───────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    check_api_key()
    cache.load_from_disk()
    scheduler.start()


@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown()


# ── Root ─────────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


# ── Feeds ────────────────────────────────────────────────────────────────────

@app.get("/api/feeds")
async def list_feeds():
    feeds = feeds_manager.read_feeds()
    return {"feeds": feeds}


class AddFeedRequest(BaseModel):
    name: str
    url: str


@app.post("/api/feeds")
async def add_feed(body: AddFeedRequest):
    loop = asyncio.get_event_loop()
    # Validate first
    validation = await loop.run_in_executor(None, fetcher.validate_feed, body.url)
    if not validation["valid"]:
        raise HTTPException(status_code=400, detail=validation.get("error", "Invalid feed"))

    result = feeds_manager.add_feed(body.name.strip(), body.url.strip())
    if not result["success"]:
        raise HTTPException(status_code=409, detail=result["error"])
    return {"success": True, "feed_title": validation.get("feed_title", "")}


@app.delete("/api/feeds/{name}")
async def delete_feed(name: str):
    result = feeds_manager.remove_feed(name)
    if not result.get("removed"):
        raise HTTPException(status_code=404, detail=f"Feed '{name}' not found")
    return {"success": True}


class ValidateRequest(BaseModel):
    url: str


@app.post("/api/feeds/validate")
async def validate_feed(body: ValidateRequest):
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, fetcher.validate_feed, body.url)
    return result


# ── Articles ─────────────────────────────────────────────────────────────────

@app.get("/api/articles")
async def get_articles():
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, fetcher.fetch_all)
    cache.set_articles(data)
    return data


# ── Briefing ─────────────────────────────────────────────────────────────────

@app.get("/api/briefing/stream")
async def briefing_stream():
    articles = cache.get_articles()
    if not articles:
        raise HTTPException(status_code=400, detail="No articles cached. Fetch articles first.")

    loop = asyncio.get_event_loop()

    def _sse_generator():
        full_text = []
        try:
            for chunk in briefing_mod.generate_briefing_stream(articles):
                full_text.append(chunk)
                yield chunk
        except Exception as e:
            err = str(e).replace("\n", " ")
            yield f"data: [ERROR] {err}\n\n"
            return
        # Persist complete briefing
        combined = "".join(full_text)
        lines = []
        for line in combined.split("\n"):
            if line.startswith("data: ") and line != "data: [DONE]":
                lines.append(line[6:].replace("\\n", "\n"))
        cache.set_briefing("".join(lines))

    return StreamingResponse(
        _sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/briefing/latest")
async def briefing_latest():
    return {
        "briefing": cache.get_briefing(),
        "generated_at": cache.get_briefing_at(),
    }


# ── Scheduler ────────────────────────────────────────────────────────────────

@app.get("/api/scheduler/status")
async def scheduler_status():
    return scheduler.get_status()


class SchedulerConfig(BaseModel):
    interval_minutes: int


@app.post("/api/scheduler/config")
async def scheduler_config(body: SchedulerConfig):
    scheduler.set_interval(body.interval_minutes)
    return scheduler.get_status()
