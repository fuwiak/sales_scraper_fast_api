# api.py
# FastAPI GET endpoint using the shared async engine.
# - orjson responses
# - start/end/page params
# - reuses one Chromium across requests
# Run:
#   uvicorn api:app --host 0.0.0.0 --port 8000 --workers 1

import asyncio
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.responses import ORJSONResponse

from scraper_engine import AllItemsScraper

# Create one global scraper (headless, resource-blocking). Reused by all requests.
scraper = AllItemsScraper(headless=True, block_resources=True)

app = FastAPI(
    title="MVBA /allitems scraper API",
    default_response_class=ORJSONResponse,
)

@app.on_event("startup")
async def _startup():
    await scraper.start()

@app.on_event("shutdown")
async def _shutdown():
    await scraper.stop()

@app.get("/scrape")
async def scrape(
    page: Optional[int] = Query(None, description="Equivalent to start=1&end=page"),
    start: Optional[int] = Query(None, ge=1),
    end: Optional[int] = Query(None, ge=1),
):
    # Resolve range
    if start is None and end is None:
        if page is None:
            start, end = 1, 1
        else:
            start, end = 1, max(1, page)
    elif start is not None and end is None:
        end = start
    elif start is None and end is not None:
        start = 1
    if end < start:
        return ORJSONResponse({"error": "end must be >= start"}, status_code=400)

    # Scrape (no progress output in API)
    data = await scraper.scrape_pages(start=start, end=end, progress_cb=None)
    # For n8n, it's convenient to return both shapes:
    # - data["ids"]      → original IDS-compatible objects
    # - data["normalized"] → human-friendly objects with stable keys
    return data
