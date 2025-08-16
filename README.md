# MVB Tax Sales Scraper

This project scrapes auction data from MVB Tax Sales website using Playwright.

## Installation

1. Create and activate virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
playwright install
```

## Usage

### Basic Scraping Commands

```bash
# Scrape all pages (default)
python main.py

# Scrape first 5 pages
python main.py --page 5

# Scrape from page 10 to 20
python main.py --start 10 --end 20

# Scrape with debug logging
python main.py --page 1 --debug

# Run with visible browser window
python main.py --page 1 --headed

# Use Chrome instead of Chromium
python main.py --page 1 --browser chrome
```

### Command Line Options

- `--page N`: Scrape from page 1 to page N
- `--start N`: Start scraping from page N (default: 1)
- `--end N`: Stop scraping at page N
- `--debug`: Enable debug logging
- `--headed`: Run with visible browser window
- `--browser`: Choose browser (chromium, chrome, firefox)

## Web Server (FastAPI + browser-use)

### Starting the server
```bash
# Make sure to set environment variables first
export OPENAI_API_KEY="your-groq-api-key"
export OPENAI_BASE_URL="https://api.groq.com/openai/v1"

# Start the server
uvicorn app_first_page:app --reload
```

### Testing the API

#### Basic endpoints
```bash
# Test if API is running
curl "http://localhost:8000/" -H "accept: application/json"

# Health check
curl "http://localhost:8000/health" -H "accept: application/json"

# View API documentation
open http://localhost:8000/docs
```

#### Scraping endpoint
```bash
# Scrape first page of auction items
curl "http://localhost:8000/scrape/first" -H "accept: application/json"
```

**Expected output format:**
```json
{
  "items": [
    {
      "title": "Account No. 12345 - Property Description",
      "url": "https://www.mvbataxsales.com/auction/...",
      "image": "https://d2jg8vcunvbhyl.cloudfront.net/...",
      "current_bid": "$1,000.00",
      "min_bid": "$500.00",
      "high_bidder": "1234",
      "time_remaining": "Closed",
      "item_location": "County, TX",
      "extras": ["WITHDRAWN FROM SALE"]
    }
  ],
  "error": null,
  "raw_output": "..."
}
```

### Killing uvicorn server

If uvicorn is running and you need to stop it:

#### Method 1: Find and kill by port
```bash
# Find the process ID running on port 8000
lsof -ti:8000

# Kill the process (replace PID with actual process ID)
kill -9 PID
```

#### Method 2: One-liner to kill uvicorn on port 8000
```bash
kill -9 $(lsof -ti:8000)
```

#### Method 3: Kill all uvicorn processes
```bash
pkill -f uvicorn
```

#### Method 4: If you know the specific app name
```bash
pkill -f "app_first_page"
```

### Alternative: Use Ctrl+C
If uvicorn is running in the foreground, simply press `Ctrl+C` to stop it gracefully.

## Output

- **CSV File**: `mvbataxsales_items.csv` - Contains scraped auction data
- **Log Files**: `logs/scrape_YYYYMMDD_HHMMSS.log` - Detailed execution logs

## Features

- ✅ Real-time logging (terminal + file)
- ✅ Deduplication (prevents duplicate entries)
- ✅ Command line parameters for flexible scraping
- ✅ Error handling and timeout management
- ✅ Multiple browser support
- ✅ Debug mode for troubleshooting

## Troubleshooting

### Common Issues

1. **Playwright not found**: Run `playwright install`
2. **Port already in use**: Use the kill commands above to stop uvicorn
3. **Virtual environment**: Make sure to activate with `source .venv/bin/activate`
