#!/bin/bash

# Start script for Railway deployment
# Single worker is optimal for the shared Chromium engine

# Use Railway's PORT environment variable or default to 8000
PORT=${PORT:-8000}

# Start the FastAPI app with uvicorn
exec uvicorn api:app \
    --host 0.0.0.0 \
    --port $PORT \
    --workers 1 \
    --loop uvloop \
    --http httptools \
    --log-level info
