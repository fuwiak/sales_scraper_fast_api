FROM python:3.10-slim

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PORT=8000

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
 && python -m playwright install --with-deps chromium

# Smoke-check to catch missing package at build time
RUN python - <<'PY'
import playwright, sys
print("python:", sys.version)
print("playwright:", playwright.__version__)
PY

COPY . .
EXPOSE 8000
CMD ["bash", "-lc", "./start.sh"]
