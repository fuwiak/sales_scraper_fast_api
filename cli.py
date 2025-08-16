# cli.py
import sys
import csv
import argparse
import asyncio
from typing import Optional

from scraper_engine import AllItemsScraper

# Colors
try:
    from rich.console import Console
    from rich.text import Text
    RICH = True
except Exception:
    RICH = False
    Console = None
    Text = None

TSV_HEADERS = [
    "pic href", "pic src", "trunc-title",
    "float-left", "float-right",
    "float-left 2", "float-right 2", "float-right 3", "float-left 4",
    "item_extra_info", "float-right 5", "red_small",
    "float-left 5", "float-left 6", "float-right 6", "float-left 7"
]

CSV_FIELDS = [
    "item_url", "image_url", "title",
    "current_bid", "min_bid", "bid_increment",
    "high_bidder", "bids",
    "time_remaining", "item_location",
    "status", "extra_info",
]

def _sanitize_tsv(v: Optional[str]) -> str:
    if v is None: return ""
    return v.replace("\t"," ").replace("\r"," ").replace("\n"," ").strip()

def _short(s: Optional[str], n: int = 96) -> str:
    if not s: return ""
    s = " ".join(s.split())
    return s if len(s) <= n else (s[: n-1] + "…")

async def main():
    ap = argparse.ArgumentParser(
        description="Fast, colorized scraper for /allitems with page range + dual outputs."
    )
    ap.add_argument("--page", type=int, help="How many 'pages' to fetch (from 1). Equivalent to --start 1 --end N.")
    ap.add_argument("--start", type=int, default=None, help="Start 'page' (min 1).")
    ap.add_argument("--end", type=int, default=None, help="End 'page' (>= start).")
    ap.add_argument("--out-tsv", type=str, help="Write IDS TSV to this file.")
    ap.add_argument("--tsv-stdout", action="store_true", help="Write IDS TSV to stdout.")
    ap.add_argument("--out-csv", type=str, help="Write normalized CSV (human-readable fields) to this file.")
    ap.add_argument("--headless", dest="headless", action="store_true", default=True, help="Run headless (default).")
    ap.add_argument("--no-headless", dest="headless", action="store_false", help="Run with visible browser window.")
    ap.add_argument("--colors", dest="colors", action="store_true", default=True, help="Color logs (default).")
    ap.add_argument("--no-colors", dest="colors", action="store_false", help="Disable color logs.")
    ap.add_argument("--progress", dest="progress", action="store_true", default=True, help="Show live progress (default).")
    ap.add_argument("--no-progress", dest="progress", action="store_false", help="Hide live progress.")
    args = ap.parse_args()

    # Resolve range
    if args.page and (args.start or args.end):
        print("Note: both --page and --start/--end provided. Using --start/--end.", file=sys.stderr)
    if args.start is None and args.end is None:
        if args.page is None:
            args.page = 1
        args.start, args.end = 1, max(1, args.page)
    elif args.start is not None and args.end is None:
        args.end = args.start
    elif args.start is None and args.end is not None:
        args.start = 1
    if args.start < 1 or args.end < args.start:
        raise SystemExit("Invalid range. Ensure start>=1 and end>=start.")

    # Outputs
    tsv_out = None
    if args.out_tsv:
        tsv_out = open(args.out_tsv, "w", encoding="utf-8", newline="")
    elif args.tsv_stdout:
        tsv_out = sys.stdout  # opt-in

    csv_out = open(args.out_csv, "w", encoding="utf-8", newline="") if args.out_csv else None
    to_close = []
    if args.out_tsv: to_close.append(tsv_out)
    if csv_out: to_close.append(csv_out)

    # Writers
    if tsv_out:
        tsv_out.write("\t".join(TSV_HEADERS) + "\n"); tsv_out.flush()
    csv_writer = None
    if csv_out:
        csv_writer = csv.DictWriter(csv_out, fieldnames=CSV_FIELDS)
        csv_writer.writeheader(); csv_out.flush()

    console = Console(stderr=True) if (args.colors and args.progress and RICH) else None

    def on_progress(idx: int, pnum: int, ids_rec, norm_rec):
        if args.progress:
            base = f"[{idx:04d}] p{pnum}  {_short(norm_rec.get('title') or ids_rec.get('pic href'))}"
            details = []
            if norm_rec.get("current_bid"): details.append(f"Current {norm_rec['current_bid']}")
            if norm_rec.get("min_bid"):     details.append(f"Min {norm_rec['min_bid']}")
            if norm_rec.get("status"):      details.append(norm_rec['status'])
            tail = "  |  ".join(details)
            if console:
                line = Text(base)
                status = (norm_rec.get("status") or "").upper()
                if "WITHDRAWN" in status:
                    line.stylize("bold red")
                elif "CLOSED" in status:
                    line.stylize("yellow")
                else:
                    line.stylize("bold white")
                if tail:
                    line.append("  "); line.append(tail, style="dim")
                console.print(line)
            else:
                msg = base + (("  " + tail) if tail else "")
                print(msg, file=sys.stderr, flush=True)

        if tsv_out:
            tsv_row = [ _sanitize_tsv(ids_rec.get(h)) for h in TSV_HEADERS ]
            tsv_out.write("\t".join(tsv_row) + "\n"); tsv_out.flush()
        if csv_writer:
            csv_writer.writerow(norm_rec); csv_out.flush()

    scraper = AllItemsScraper(headless=args.headless, block_resources=True)
    try:
        await scraper.scrape_pages(args.start, args.end, progress_cb=on_progress)
    finally:
        for f in to_close:
            f.close()
        await scraper.stop()

if __name__ == "__main__":
    asyncio.run(main())
