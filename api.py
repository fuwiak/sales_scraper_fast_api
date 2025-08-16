from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from typing import Optional
from allitems_cli import (  # reuse extraction & normalization from the CLI file
    ALLITEMS_URL, ITEM_ANCHOR_SELECTOR,
    try_click_any, autoscroll_until_stall,
    extract_ids_style_record, normalize_record
)
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

app = FastAPI(title="MVBA /allitems scraper API")

@app.get("/scrape")
def scrape(
    page: Optional[int] = Query(None, description="Equivalent to start=1&end=page"),
    start: Optional[int] = Query(None, ge=1),
    end: Optional[int] = Query(None, ge=1),
    headless: bool = Query(True),
):
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
        return JSONResponse({"error": "end cannot be smaller than start"}, status_code=400)

    ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/124 Safari/537.36")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent=ua,
            viewport={"width": 1400, "height": 900},
            java_script_enabled=True,
            timezone_id="America/Chicago",
            locale="en-US",
        )
        page_obj = context.new_page()
        page_obj.goto(ALLITEMS_URL, wait_until="domcontentloaded", timeout=45_000)
        try:
            page_obj.wait_for_selector(ITEM_ANCHOR_SELECTOR, timeout=20_000)
        except PWTimeout:
            pass

        autoscroll_until_stall(page_obj, 0.8, 2)

        seen = set()
        current_page = 1
        items = []

        def collect(pnum: int):
            anchors = page_obj.locator(ITEM_ANCHOR_SELECTOR)
            n = anchors.count()
            for i in range(n):
                a = anchors.nth(i)
                ids_rec, lefts, rights, root = extract_ids_style_record(page_obj, a)
                href = ids_rec.get("pic href")
                if not href or href in seen: 
                    continue
                seen.add(href)
                norm = normalize_record(ids_rec, lefts, rights, root)
                payload = {
                    "page": pnum,
                    "ids": ids_rec,
                    "normalized": norm,
                }
                items.append(payload)

        # page 1
        collect(current_page)

        while current_page < end:
            progressed = False
            if try_click_any(page_obj, [
                "button:has-text('Load more')","a:has-text('Load more')","button:has-text('Show more')",
                ".load-more, button.load-more, a.load-more"
            ]):
                page_obj.wait_for_timeout(800)
                autoscroll_until_stall(page_obj, 0.8, 2)
                current_page += 1
                collect(current_page)
                progressed = True

            if not progressed and try_click_any(page_obj, [
                "a[rel='next']","button:has-text('Next')","a:has-text('Next')",
                ".pagination .next a, .pagination-next a, a.pagination-next"
            ]):
                try:
                    page_obj.wait_for_load_state("domcontentloaded", timeout=20_000)
                except PWTimeout:
                    pass
                autoscroll_until_stall(page_obj, 0.8, 2)
                current_page += 1
                collect(current_page)
                progressed = True

            if not progressed:
                before = page_obj.locator(ITEM_ANCHOR_SELECTOR).count()
                autoscroll_until_stall(page_obj, 0.8, 2)
                after = page_obj.locator(ITEM_ANCHOR_SELECTOR).count()
                if after > before:
                    current_page += 1
                    collect(current_page)
                    progressed = True

            if not progressed:
                break

        context.close()
        browser.close()

    return JSONResponse({
        "source_url": ALLITEMS_URL,
        "start": start, "end": end,
        "items_count": len(items),
        "items": items,
    })
