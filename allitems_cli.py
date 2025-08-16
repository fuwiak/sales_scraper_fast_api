import sys, time, random, argparse, csv, re
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin, urldefrag

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# Pretty console (colors)
try:
    from rich.console import Console
    from rich.text import Text
    RICH_AVAILABLE = True
except Exception:
    RICH_AVAILABLE = False
    Console = None
    Text = None

ALLITEMS_URL = "https://www.mvbataxsales.com/allitems"

# Heuristic selectors (kept generic to survive layout tweaks)
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

# IDS-style TSV headers (exact strings)
TSV_HEADERS = [
    "pic href", "pic src", "trunc-title",
    "float-left", "float-right",
    "float-left 2", "float-right 2", "float-right 3", "float-left 4",
    "item_extra_info", "float-right 5", "red_small",
    "float-left 5", "float-left 6", "float-right 6", "float-left 7"
]

# Normalized readable field names
CSV_FIELDS = [
    "item_url", "image_url", "title",
    "current_bid", "min_bid", "bid_increment",
    "high_bidder", "bids",
    "time_remaining", "item_location",
    "status", "extra_info",
]

BIDS_RE = re.compile(r"\(bids:\s*([0-9]+)\)", re.I)
DOLLAR_RE = re.compile(r"\$\s?[\d,]+(?:\.\d{2})?")

def norm_space(s: Optional[str]) -> Optional[str]:
    if s is None: return None
    return " ".join(s.split())

def sanitize_tsv_field(v: Optional[str]) -> str:
    # Keep TSV clean but readable
    if v is None: return ""
    return v.replace("\t", " ").replace("\r", " ").replace("\n", " ").strip()

def try_click_any(page, selectors: List[str]) -> bool:
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if el.count() > 0 and el.is_visible():
                el.click()
                return True
        except Exception:
            continue
    return False

def autoscroll_until_stall(page, scroll_pause: float, max_rounds_no_new: int) -> Tuple[int, int]:
    """Scroll down until the number of item anchors stops growing for a few rounds."""
    rounds_without_growth = 0
    last_cnt = page.locator(ITEM_ANCHOR_SELECTOR).count()
    total_scrolls = 0
    while rounds_without_growth < max_rounds_no_new:
        try:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        except Exception:
            break
        page.wait_for_timeout(int(scroll_pause * 1000))
        total_scrolls += 1
        new_cnt = page.locator(ITEM_ANCHOR_SELECTOR).count()
        if new_cnt <= last_cnt:
            rounds_without_growth += 1
        else:
            rounds_without_growth = 0
            last_cnt = new_cnt
        if total_scrolls > 200:
            break
    return last_cnt, total_scrolls

def txt(el) -> Optional[str]:
    try:
        t = el.inner_text().strip()
        return t if t else None
    except Exception:
        return None

def attr(el, name: str) -> Optional[str]:
    try:
        v = el.get_attribute(name)
        return v.strip() if v else None
    except Exception:
        return None

def nearest_card_root(a_loc):
    # Try to find a container block ("card") for the anchor
    candidates_xpath = (
        "xpath=ancestor::*["
        "contains(@class,'card') or contains(@class,'item') or contains(@class,'list') "
        "or contains(@class,'row') or contains(@class,'column') or contains(@class,'listview')"
        "][1]"
    )
    try:
        loc = a_loc.locator(candidates_xpath)
        return loc if loc.count() > 0 else a_loc
    except Exception:
        return a_loc

def extract_ids_style_record(page, a_loc) -> Dict[str, Optional[str]]:
    """Return a dict with IDS-style keys."""
    href = attr(a_loc, "href")
    if href:
        href = urljoin(ALLITEMS_URL, href)
        href, _ = urldefrag(href)

    img_src = None
    try:
        img = a_loc.locator("img").first
        if img.count() > 0:
            img_src = attr(img, "src") or attr(img, "data-src")
            if img_src:
                img_src = urljoin(ALLITEMS_URL, img_src)
    except Exception:
        pass

    root = nearest_card_root(a_loc)

    # title
    trunc_title = None
    try:
        tloc = root.locator(".trunc-title").first
        trunc_title = txt(tloc) if tloc.count() > 0 else txt(a_loc)
    except Exception:
        trunc_title = txt(a_loc)

    # collect float-left / float-right buckets in order
    lefts, rights = [], []
    try:
        lc = root.locator(".float-left").count()
        for i in range(lc):
            lefts.append(txt(root.locator(".float-left").nth(i)))
    except Exception:
        pass
    try:
        rc = root.locator(".float-right").count()
        for i in range(rc):
            rights.append(txt(root.locator(".float-right").nth(i)))
    except Exception:
        pass

    # extra info
    item_extra_info = None
    try:
        ie = root.locator(".item_extra_info").first
        if ie.count() > 0:
            item_extra_info = txt(ie)
    except Exception:
        pass

    red_small = None
    try:
        rs = root.locator(".red_small").first
        if rs.count() > 0:
            red_small = txt(rs)
    except Exception:
        pass

    def pick(arr, idx):
        try:
            return arr[idx] if idx < len(arr) else None
        except Exception:
            return None

    return {
        "pic href": href,
        "pic src": img_src,
        "trunc-title": trunc_title,
        "float-left": pick(lefts, 0),
        "float-right": pick(rights, 0),
        "float-left 2": pick(lefts, 1),
        "float-right 2": pick(rights, 1),
        "float-right 3": pick(rights, 2),
        "float-left 4": pick(lefts, 3),
        "item_extra_info": item_extra_info,
        "float-right 5": pick(rights, 4),
        "red_small": red_small,
        "float-left 5": pick(lefts, 4),
        "float-left 6": pick(lefts, 5),
        "float-right 6": pick(rights, 5),
        "float-left 7": pick(lefts, 6),
    }, lefts, rights, root

def normalize_record(ids_rec: Dict[str, Optional[str]], lefts: List[Optional[str]], rights: List[Optional[str]], root) -> Dict[str, Optional[str]]:
    """
    Best-effort mapping of label/value pairs into readable fields.
    We scan float-left/right pairs, plus card text, to infer common fields.
    """
    # Base fields
    norm: Dict[str, Optional[str]] = {
        "item_url": ids_rec.get("pic href"),
        "image_url": ids_rec.get("pic src"),
        "title": ids_rec.get("trunc-title"),
        "current_bid": None,
        "min_bid": None,
        "bid_increment": None,
        "high_bidder": None,
        "bids": None,
        "time_remaining": None,
        "item_location": None,
        "status": None,
        "extra_info": ids_rec.get("item_extra_info") or ids_rec.get("red_small"),
    }

    # Build label->value mapping from left/right lists
    pairs: List[Tuple[str, Optional[str]]] = []
    for i, lbl in enumerate(lefts):
        if not lbl: 
            continue
        val = rights[i] if i < len(rights) else None
        pairs.append((lbl.strip().rstrip(':'), norm_space(val)))

    # Scan pairs for known labels
    for label, value in pairs:
        low = label.lower()
        if "current bid" in low:
            norm["current_bid"] = value
        elif "min bid" in low:
            norm["min_bid"] = value
        elif "high bidder" in low:
            norm["high_bidder"] = value
        elif "time remaining" in low:
            norm["time_remaining"] = value
        elif "item location" in low:
            norm["item_location"] = value

    # Try to derive "bids" from the whole card text
    try:
        card_text = root.inner_text().strip()
    except Exception:
        card_text = " ".join(filter(None, lefts + rights))
    m = BIDS_RE.search(card_text or "")
    if m:
        norm["bids"] = m.group(1)

    # Status detection (very common on this site)
    text_all = " ".join([
        str(norm.get("extra_info") or ""),
        str(ids_rec.get("red_small") or ""),
        card_text or "",
        ids_rec.get("trunc-title") or "",
    ]).upper()
    if "WITHDRAWN" in text_all:
        norm["status"] = "WITHDRAWN"
    elif "CLOSED" in text_all:
        norm["status"] = "CLOSED"

    # Try to guess bid increment if we have multiple dollar amounts w/o labels
    # e.g., we already got current/min; look for a third $ that isn't assigned.
    dollars = DOLLAR_RE.findall(text_all)
    if dollars:
        # unique while preserving order
        uniq = []
        for d in dollars:
            if d not in uniq:
                uniq.append(d)
        known = {norm.get("current_bid"), norm.get("min_bid")}
        unknown = [d for d in uniq if d not in known and d]
        if unknown:
            norm["bid_increment"] = unknown[0]

    # If location text itself is a status marker, reflect it
    if norm.get("item_location"):
        loc_up = norm["item_location"].upper()
        if "WITHDRAWN" in loc_up:
            norm["status"] = "WITHDRAWN"

    return {k: (norm_space(v) if isinstance(v, str) else v) for k, v in norm.items()}

def write_tsv_row(out, rec: Dict[str, Optional[str]]):
    row = [sanitize_tsv_field(rec.get(h)) for h in TSV_HEADERS]
    out.write("\t".join(row) + "\n")

def shorten(s: Optional[str], n: int = 96) -> str:
    if not s: return ""
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 1] + "…"

def run_scrape(start_page: int, end_page: int, headless: bool, out_tsv: Optional[str], out_csv: Optional[str], progress: bool, colors: bool):
    if end_page < start_page:
        raise SystemExit("--end cannot be smaller than --start")

    # Outputs
    tsv_out = sys.stdout if not out_tsv else open(out_tsv, "w", encoding="utf-8", newline="")
    csv_out = open(out_csv, "w", encoding="utf-8", newline="") if out_csv else None
    must_close = []
    if out_tsv: must_close.append(tsv_out)
    if csv_out: must_close.append(csv_out)

    # Write IDS TSV header
    tsv_out.write("\t".join(TSV_HEADERS) + "\n"); tsv_out.flush()

    # Prepare normalized CSV writer
    csv_writer = None
    if csv_out:
        csv_writer = csv.DictWriter(csv_out, fieldnames=CSV_FIELDS)
        csv_writer.writeheader(); csv_out.flush()

    # Pretty console on stderr
    console = Console(stderr=True) if (progress and colors and RICH_AVAILABLE) else None
    plain_progress = progress and not console

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
        page = context.new_page()

        page.goto(ALLITEMS_URL, wait_until="domcontentloaded", timeout=45_000)
        try:
            page.wait_for_selector(ITEM_ANCHOR_SELECTOR, timeout=20_000)
        except PWTimeout:
            pass

        seen_hrefs = set()
        current_page = 1
        item_idx = 1

        autoscroll_until_stall(page, 0.8, 2)

        def log_line(idx: int, pnum: int, title: str, status: Optional[str], cur: Optional[str], minb: Optional[str]):
            if not progress: 
                return
            # Build a colored status line
            base = f"[{idx:04d}] p{pnum}  {shorten(title)}"
            suffix = []
            if cur:  suffix.append(f"Current {cur}")
            if minb: suffix.append(f"Min {minb}")
            if status: suffix.append(status)
            postfix = "  |  ".join(suffix)
            if console:
                seg = Text(base)
                # Status coloring
                if status and "WITHDRAWN" in status.upper():
                    seg.stylize("bold red")
                elif status and "CLOSED" in status.upper():
                    seg.stylize("yellow")
                else:
                    seg.stylize("bold white")
                # Details
                if postfix:
                    seg.append("  ")
                    seg.append(postfix, style="dim")
                console.print(seg)
            else:
                sys.stderr.write(base + ("  " + postfix if postfix else "") + "\n"); sys.stderr.flush()

        def collect(page_idx: int):
            nonlocal item_idx
            anchors = page.locator(ITEM_ANCHOR_SELECTOR)
            n = anchors.count()
            for i in range(n):
                a = anchors.nth(i)
                href = attr(a, "href")
                if not href:
                    continue
                href = urljoin(ALLITEMS_URL, href)
                href, _ = urldefrag(href)
                if href in seen_hrefs:
                    continue
                seen_hrefs.add(href)

                ids_rec, lefts, rights, root = extract_ids_style_record(page, a)
                # Write IDS TSV
                write_tsv_row(tsv_out, ids_rec)
                # Normalize and (optionally) write CSV
                norm = normalize_record(ids_rec, lefts, rights, root)
                if csv_writer:
                    csv_writer.writerow(norm)

                # Live log
                log_line(
                    item_idx, page_idx,
                    norm.get("title") or ids_rec.get("pic href") or "",
                    norm.get("status"),
                    norm.get("current_bid"),
                    norm.get("min_bid"),
                )
                item_idx += 1
            tsv_out.flush()
            if csv_out: csv_out.flush()

        # Page 1
        if progress:
            if console: console.print(Text(f"==> Start p{current_page}", style="cyan"))
            else: sys.stderr.write(f"==> Start p{current_page}\n")
        collect(current_page)

        # Next pages
        while current_page < end_page:
            progressed = False

            if try_click_any(page, LOAD_MORE_CANDIDATES):
                page.wait_for_timeout(800)
                autoscroll_until_stall(page, 0.8, 2)
                current_page += 1
                if progress:
                    msg = f"==> Loaded p{current_page} (load-more)"
                    console.print(Text(msg, style="cyan")) if console else sys.stderr.write(msg + "\n")
                collect(current_page)
                progressed = True

            if not progressed and try_click_any(page, NEXT_PAGE_CANDIDATES):
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=20_000)
                except PWTimeout:
                    pass
                autoscroll_until_stall(page, 0.8, 2)
                current_page += 1
                if progress:
                    msg = f"==> Loaded p{current_page} (next)"
                    console.print(Text(msg, style="cyan")) if console else sys.stderr.write(msg + "\n")
                collect(current_page)
                progressed = True

            if not progressed:
                before = page.locator(ITEM_ANCHOR_SELECTOR).count()
                autoscroll_until_stall(page, 0.8, 2)
                after = page.locator(ITEM_ANCHOR_SELECTOR).count()
                if after > before:
                    current_page += 1
                    if progress:
                        msg = f"==> Loaded p{current_page} (scroll)"
                        console.print(Text(msg, style="cyan")) if console else sys.stderr.write(msg + "\n")
                    collect(current_page)
                    progressed = True

            if not progressed:
                if progress:
                    msg = "==> No further pagination progress — stopping."
                    console.print(Text(msg, style="magenta")) if console else sys.stderr.write(msg + "\n")
                break

            page.wait_for_timeout(random.randint(500, 1000))

        context.close()
        browser.close()

    for f in must_close:
        f.close()

def parse_args():
    ap = argparse.ArgumentParser(
        description="Colorful CLI scraper for https://www.mvbataxsales.com/allitems with page range, live index, and dual outputs."
    )
    ap.add_argument("--page", type=int, help="How many 'pages' to fetch (from 1). Equivalent to --start 1 --end N.")
    ap.add_argument("--start", type=int, help="Start 'page' (min 1).", default=None)
    ap.add_argument("--end", type=int, help="End 'page' (>= start).", default=None)
    ap.add_argument("--out-tsv", type=str, help="Output file for IDS-style TSV (default: stdout if not set).")
    ap.add_argument("--out-csv", type=str, help="Output file for normalized CSV (human-readable field names).")
    ap.add_argument("--headless", dest="headless", action="store_true", default=True, help="Run headless (default).")
    ap.add_argument("--no-headless", dest="headless", action="store_false", help="Run with a visible browser window.")
    ap.add_argument("--progress", dest="progress", action="store_true", default=True, help="Show live log (default).")
    ap.add_argument("--no-progress", dest="progress", action="store_false", help="Hide live log.")
    ap.add_argument("--colors", dest="colors", action="store_true", default=True, help="Use colored logs (default).")
    ap.add_argument("--no-colors", dest="colors", action="store_false", help="Disable colored logs.")
    args = ap.parse_args()

    if args.page and (args.start or args.end):
        sys.stderr.write("Note: both --page and --start/--end provided. Using --start/--end.\n")
    if args.start is None and args.end is None:
        if args.page is None:
            args.page = 1
        args.start, args.end = 1, max(1, args.page)
    elif args.start is not None and args.end is None:
        args.end = args.start
    elif args.start is None and args.end is not None:
        args.start = 1

    if args.start < 1: raise SystemExit("--start must be >= 1")
    if args.end < 1: raise SystemExit("--end must be >= 1")
    if args.end < args.start: raise SystemExit("--end cannot be smaller than --start")

    # If no --out-tsv, default to stdout TSV
    if not args.out_tsv:
        # nothing to do; TSV goes to stdout
        pass
    return args

if __name__ == "__main__":
    a = parse_args()
    run_scrape(
        start_page=a.start,
        end_page=a.end,
        headless=a.headless,
        out_tsv=a.out_tsv,
        out_csv=a.out_csv,
        progress=a.progress,
        colors=a.colors,
    )
