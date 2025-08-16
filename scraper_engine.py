# scraper_engine.py
import asyncio
import re
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urldefrag

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, TimeoutError as PWTimeout

ALLITEMS_URL = "https://www.mvbataxsales.com/allitems"

ITEM_ANCHOR_SELECTOR = "a[href*='/auction/'][href*='/item/']:has(img)"
LOAD_MORE_CANDIDATES = [
    "button:has-text('Load more')",
    "a:has-text('Load more')",
    "button:has-text('Show more')",
    ".load-more, button.load-more, a.load-more",
]
NEXT_PAGE_CANDIDATES = [
    "a[rel='next']",
    "button:has-text('Next')",
    "a:has-text('Next')",
    ".pagination .next a, .pagination-next a, a.pagination-next",
]

DOLLAR_RE = re.compile(r"\$\s?[\d,]+(?:\.\d{2})?")
BIDS_RE = re.compile(r"\(bids:\s*([0-9]+)\)", re.I)

def _norm_space(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    return " ".join(s.split())

def _pick(arr: List[Optional[str]], idx: int) -> Optional[str]:
    return arr[idx] if idx < len(arr) else None

class AllItemsScraper:
    """Async scraper reusing a single Chromium instance."""
    def __init__(
        self,
        headless: bool = True,
        default_timeout_ms: int = 30_000,
        timezone_id: str = "America/Chicago",
        locale: str = "en-US",
        user_agent: str = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124 Safari/537.36"
        ),
        block_resources: bool = True,
    ):
        self.headless = headless
        self.default_timeout_ms = default_timeout_ms
        self.timezone_id = timezone_id
        self.locale = locale
        self.user_agent = user_agent
        self.block_resources = block_resources

        self._pw = None
        self._browser: Optional[Browser] = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        async with self._lock:
            if self._browser is not None:
                return
            self._pw = await async_playwright().start()
            self._browser = await self._pw.chromium.launch(headless=self.headless)

    async def stop(self) -> None:
        async with self._lock:
            if self._browser is not None:
                await self._browser.close()
                self._browser = None
            if self._pw is not None:
                await self._pw.stop()
                self._pw = None

    async def _new_context(self) -> BrowserContext:
        assert self._browser is not None, "Call start() first."
        ctx = await self._browser.new_context(
            user_agent=self.user_agent,
            viewport={"width": 1400, "height": 900},
            java_script_enabled=True,
            timezone_id=self.timezone_id,
            locale=self.locale,
        )
        # IMPORTANT: these are synchronous in Playwright's Python API
        ctx.set_default_timeout(self.default_timeout_ms)
        ctx.set_default_navigation_timeout(self.default_timeout_ms)

        if self.block_resources:
            async def _route(route, request):
                rtype = request.resource_type
                if rtype in ("image", "media", "font", "stylesheet"):
                    await route.abort()
                else:
                    await route.continue_()
            await ctx.route("**/*", _route)

        return ctx

    async def _autoscroll_until_stall(self, page: Page, scroll_pause_s: float = 0.6, max_rounds_no_new: int = 2) -> Tuple[int, int]:
        last_cnt = await page.locator(ITEM_ANCHOR_SELECTOR).count()
        rounds = 0
        total_scrolls = 0
        while rounds < max_rounds_no_new:
            try:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            except Exception:
                break
            await page.wait_for_timeout(int(scroll_pause_s * 1000))
            total_scrolls += 1
            new_cnt = await page.locator(ITEM_ANCHOR_SELECTOR).count()
            if new_cnt <= last_cnt:
                rounds += 1
            else:
                rounds = 0
                last_cnt = new_cnt
            if total_scrolls > 200:
                break
        return last_cnt, total_scrolls

    async def _try_click_any(self, page: Page, selectors: List[str]) -> bool:
        for sel in selectors:
            try:
                el = page.locator(sel).first
                if await el.count() > 0 and await el.is_visible():
                    await el.click()
                    return True
            except Exception:
                continue
        return False

    async def _extract_items_js(self, page: Page) -> List[Dict[str, Any]]:
        js = """
(() => {
  const anchors = Array.from(document.querySelectorAll("a[href*='/auction/'][href*='/item/']")).filter(a => a.querySelector('img'));
  const pickText = (el) => (el && el.innerText ? el.innerText.trim() : null);
  const nearestCardRoot = (a) => {
    let el = a;
    for (let i = 0; i < 6; i++) {
      if (!el) break;
      const cls = el.className || "";
      if (typeof cls === "string" && (cls.includes("card") || cls.includes("item") || cls.includes("list") || cls.includes("row") || cls.includes("column") || cls.includes("listview"))) {
        return el;
      }
      el = el.parentElement;
    }
    return a;
  };
  const out = [];
  for (const a of anchors) {
    const href = a.getAttribute('href') || null;
    const img = a.querySelector('img');
    const imgSrc = (img && (img.getAttribute('src') || img.getAttribute('data-src'))) || null;
    const root = nearestCardRoot(a);
    const truncEl = root.querySelector('.trunc-title');
    const trunc = (truncEl && truncEl.innerText.trim()) || a.innerText.trim() || null;
    const lefts = []; root.querySelectorAll('.float-left').forEach(n => lefts.push(pickText(n)));
    const rights = []; root.querySelectorAll('.float-right').forEach(n => rights.push(pickText(n)));
    const itemExtraEl = root.querySelector('.item_extra_info');
    const redSmallEl  = root.querySelector('.red_small');
    out.push({
      picHref: href,
      picSrc: imgSrc,
      truncTitle: trunc,
      lefts, rights,
      itemExtraInfo: pickText(itemExtraEl),
      redSmall: pickText(redSmallEl),
      cardText: pickText(root)
    });
  }
  return out;
})();
        """
        items = await page.evaluate(js)
        for it in items:
            if it.get("picHref"):
                absu = urljoin(ALLITEMS_URL, it["picHref"])
                it["picHref"], _ = urldefrag(absu)
            if it.get("picSrc"):
                it["picSrc"] = urljoin(ALLITEMS_URL, it["picSrc"])
        return items

    def _normalize_record(self, it: Dict[str, Any]) -> Dict[str, Optional[str]]:
        lefts: List[Optional[str]] = it.get("lefts") or []
        rights: List[Optional[str]] = it.get("rights") or []
        def pair(i: int) -> Tuple[Optional[str], Optional[str]]:
            return _pick(lefts, i), _pick(rights, i)

        pairs: List[Tuple[str, Optional[str]]] = []
        for i, lbl in enumerate(lefts):
            if not lbl: continue
            val = rights[i] if i < len(rights) else None
            pairs.append((lbl.strip().rstrip(":"), _norm_space(val)))

        norm: Dict[str, Optional[str]] = {
            "item_url": it.get("picHref"),
            "image_url": it.get("picSrc"),
            "title": _norm_space(it.get("truncTitle")),
            "current_bid": None,
            "min_bid": None,
            "bid_increment": None,
            "high_bidder": None,
            "bids": None,
            "time_remaining": None,
            "item_location": None,
            "status": None,
            "extra_info": _norm_space(it.get("itemExtraInfo") or it.get("redSmall")),
        }

        for label, value in pairs:
            low = label.lower()
            if "current bid" in low:   norm["current_bid"] = value
            elif "min bid" in low:     norm["min_bid"] = value
            elif "high bidder" in low: norm["high_bidder"] = value
            elif "time remaining" in low: norm["time_remaining"] = value
            elif "item location" in low:  norm["item_location"] = value

        card_text = it.get("cardText") or ""
        m = BIDS_RE.search(card_text)
        if m:
            norm["bids"] = m.group(1)

        text_all = " ".join([
            it.get("itemExtraInfo") or "",
            it.get("redSmall") or "",
            card_text,
            it.get("truncTitle") or "",
        ]).upper()
        if "WITHDRAWN" in text_all:
            norm["status"] = "WITHDRAWN"
        elif "CLOSED" in text_all:
            norm["status"] = "CLOSED"

        dollars = DOLLAR_RE.findall(text_all)
        if dollars:
            uniq = []
            for d in dollars:
                if d not in uniq: uniq.append(d)
            known = {norm.get("current_bid"), norm.get("min_bid")}
            unknown = [d for d in uniq if d not in known and d]
            if unknown:
                norm["bid_increment"] = unknown[0]

        if norm.get("item_location") and "WITHDRAWN" in norm["item_location"].upper():
            norm["status"] = "WITHDRAWN"

        return {k: (_norm_space(v) if isinstance(v, str) else v) for k, v in norm.items()}

    async def scrape_pages(
        self,
        start: int = 1,
        end: int = 1,
        progress_cb: Optional[Callable[[int, int, Dict[str, Any], Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        if start < 1 or end < start:
            raise ValueError("Invalid range: start must be >=1 and end >= start")

        await self.start()
        ctx = await self._new_context()
        page = await ctx.new_page()
        await page.goto(ALLITEMS_URL, wait_until="domcontentloaded")
        try:
            await page.wait_for_selector(ITEM_ANCHOR_SELECTOR, timeout=20_000)
        except PWTimeout:
            pass

        await self._autoscroll_until_stall(page, 0.6, 2)

        seen: set[str] = set()
        current_page = 1
        idx = 1

        ids_items: List[Dict[str, Any]] = []
        norm_items: List[Dict[str, Any]] = []

        async def collect(pnum: int):
            nonlocal idx
            items = await self._extract_items_js(page)
            # de-duplicate across pages regardless of start
            new_items = []
            for it in items:
                href = it.get("picHref")
                if not href or href in seen:
                    continue
                seen.add(href)
                new_items.append(it)

            # Only record/output if pnum is within requested range
            if pnum < start:
                return

            for it in new_items:
                lefts = it.get("lefts") or []
                rights = it.get("rights") or []
                ids_rec = {
                    "pic href": it.get("picHref"),
                    "pic src": it.get("picSrc"),
                    "trunc-title": it.get("truncTitle"),
                    "float-left": _pick(lefts, 0),
                    "float-right": _pick(rights, 0),
                    "float-left 2": _pick(lefts, 1),
                    "float-right 2": _pick(rights, 1),
                    "float-right 3": _pick(rights, 2),
                    "float-left 4": _pick(lefts, 3),
                    "item_extra_info": it.get("itemExtraInfo"),
                    "float-right 5": _pick(rights, 4),
                    "red_small": it.get("redSmall"),
                    "float-left 5": _pick(lefts, 4),
                    "float-left 6": _pick(lefts, 5),
                    "float-right 6": _pick(rights, 5),
                    "float-left 7": _pick(lefts, 6),
                }
                norm = self._normalize_record(it)

                ids_items.append(ids_rec)
                norm_items.append(norm)

                if progress_cb:
                    try:
                        progress_cb(idx, pnum, ids_rec, norm)
                    except Exception:
                        pass
                idx += 1

        # Page 1
        await collect(current_page)

        # Next pages up to 'end'
        while current_page < end:
            progressed = False

            if await self._try_click_any(page, LOAD_MORE_CANDIDATES):
                await page.wait_for_timeout(700)
                await self._autoscroll_until_stall(page, 0.6, 2)
                current_page += 1
                await collect(current_page)
                progressed = True

            if not progressed and await self._try_click_any(page, NEXT_PAGE_CANDIDATES):
                try:
                    await page.wait_for_load_state("domcontentloaded", timeout=20_000)
                except PWTimeout:
                    pass
                await self._autoscroll_until_stall(page, 0.6, 2)
                current_page += 1
                await collect(current_page)
                progressed = True

            if not progressed:
                before = await page.locator(ITEM_ANCHOR_SELECTOR).count()
                await self._autoscroll_until_stall(page, 0.6, 2)
                after = await page.locator(ITEM_ANCHOR_SELECTOR).count()
                if after > before:
                    current_page += 1
                    await collect(current_page)
                    progressed = True

            if not progressed:
                break

        await ctx.close()
        return {
            "source_url": ALLITEMS_URL,
            "start": start,
            "end": end,
            "items_count": len(ids_items),
            "ids": ids_items,
            "normalized": norm_items,
        }
