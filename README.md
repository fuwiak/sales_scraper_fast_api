# Sales Scraper FastAPI

A comprehensive web scraper for MVB Tax Sales auction data with both CLI and FastAPI interfaces using Playwright for robust data extraction.

## Features

- 🚀 **FastAPI REST API** for web service integration
- 💻 **CLI tool** for direct command-line usage
- 🎭 **Playwright-based** scraping with real browser automation
- 📊 **Dual output formats**: IDS-style TSV and normalized CSV
- 🔄 **Intelligent pagination** with multiple fallback strategies
- 🎨 **Rich console output** with colored progress indicators
- 📝 **Comprehensive logging** to files and console
- 🔍 **Deduplication** to prevent duplicate entries
- ⚙️ **Configurable parameters** for flexible scraping

## Installation

1. **Create and activate virtual environment:**
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
playwright install
```

## CLI Usage

The main CLI tool is `allitems_cli.py` which provides comprehensive scraping capabilities.

### Basic Commands

```bash
# Scrape first page (default)
python allitems_cli.py

# Scrape first 5 pages
python allitems_cli.py --page 5

# Scrape pages 10-20
python allitems_cli.py --start 10 --end 20

# Run with visible browser (for debugging)
python allitems_cli.py --no-headless --page 1

# Save outputs to specific files
python allitems_cli.py --out-tsv data.tsv --out-csv data.csv --page 3

# Silent mode (no progress output)
python allitems_cli.py --no-progress --page 2
```

### CLI Options

- `--page N`: Scrape from page 1 to page N
- `--start N`: Start scraping from page N (default: 1)  
- `--end N`: Stop scraping at page N
- `--out-tsv FILE`: Output IDS-style TSV to file (default: stdout)
- `--out-csv FILE`: Output normalized CSV to file
- `--headless/--no-headless`: Run with/without visible browser
- `--progress/--no-progress`: Show/hide live progress
- `--colors/--no-colors`: Enable/disable colored output

## FastAPI Web Service

### Starting the Server

```bash
# Start the FastAPI server
uvicorn api:app --reload

# Server will be available at http://localhost:8000
```

### API Endpoints

#### Scrape Data
```bash
# Scrape first page
curl "http://localhost:8000/scrape"

# Scrape first 5 pages
curl "http://localhost:8000/scrape?page=5"

# Scrape specific range
curl "http://localhost:8000/scrape?start=2&end=4"

# Run with visible browser
curl "http://localhost:8000/scrape?headless=false"
```

#### API Documentation
- **Interactive docs**: http://localhost:8000/docs
- **OpenAPI spec**: http://localhost:8000/openapi.json

### API Response Format

```json
{
  "source_url": "https://www.mvbataxsales.com/allitems",
  "start": 1,
  "end": 1,
  "items_count": 42,
  "items": [
    {
      "page": 1,
      "ids": {
        "pic href": "https://www.mvbataxsales.com/auction/...",
        "pic src": "https://image-url...",
        "trunc-title": "Account No. R000123456 - Property Description",
        "float-left": "Current Bid",
        "float-right": "$1,500.00",
        ...
      },
      "normalized": {
        "item_url": "https://www.mvbataxsales.com/auction/...",
        "image_url": "https://image-url...",
        "title": "Account No. R000123456 - Property Description",
        "current_bid": "$1,500.00",
        "min_bid": "$500.00",
        "high_bidder": "1234",
        "time_remaining": "3 days",
        "item_location": "Harrison County, TX",
        "status": null,
        "extra_info": null
      }
    }
  ]
}
```

## Output Files

The scraper generates multiple output formats:

### IDS-Style TSV (`--out-tsv`)
Raw extraction with original field names:
- `pic href`, `pic src`, `trunc-title`
- `float-left`, `float-right` (multiple columns)
- `item_extra_info`, `red_small`

### Normalized CSV (`--out-csv`)
Human-readable format with standardized fields:
- `item_url`, `image_url`, `title`
- `current_bid`, `min_bid`, `bid_increment`
- `high_bidder`, `bids`, `time_remaining`
- `item_location`, `status`, `extra_info`

## Data Extraction Details

### Target Website
- **URL**: https://www.mvbataxsales.com/allitems
- **Content**: Texas property tax sale auction listings

### Extraction Strategy
1. **Smart pagination**: Detects and handles multiple pagination types
2. **Auto-scrolling**: Loads all items via infinite scroll
3. **Robust selectors**: Uses multiple fallback CSS selectors
4. **Data normalization**: Maps raw HTML elements to structured fields
5. **Status detection**: Identifies WITHDRAWN, CLOSED items
6. **Deduplication**: Prevents processing same items multiple times

### Pagination Methods
The scraper tries multiple pagination strategies:
1. "Load more" buttons
2. "Next" page links  
3. Infinite scroll detection
4. Auto-scroll until content stops loading

## Troubleshooting

### Common Issues

**Playwright installation:**
```bash
playwright install
```

**Port conflicts (FastAPI):**
```bash
# Kill existing uvicorn processes
pkill -f uvicorn
# Or kill specific port
kill -9 $(lsof -ti:8000)
```

**Browser issues:**
- Use `--no-headless` to see what's happening
- Check browser console for JavaScript errors
- Verify network connectivity to target site

**Output issues:**
- Ensure write permissions for output directories
- Check disk space for large scraping jobs
- Use `--no-progress` for cleaner stdout piping

### Debugging

Enable verbose output and visible browser:
```bash
python allitems_cli.py --no-headless --page 1 --colors
```

For API debugging, check FastAPI logs and use the interactive docs at `/docs`.

## Project Structure

```
├── allitems_cli.py     # Main CLI scraper tool
├── api.py              # FastAPI web service
├── requirements.txt    # Python dependencies
├── items_3_5.tsv      # Sample IDS-style output
├── items_normalized.csv # Sample normalized output
├── logs/              # Execution logs (gitignored)
├── output/            # Scraped data (gitignored)
└── README.md          # This file
```
