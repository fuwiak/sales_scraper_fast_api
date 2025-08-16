# Playwright Python base with browsers (v1.54)
FROM mcr.microsoft.com/playwright/python:v1.54.0-jammy

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ✅ Robust smoke check (no reliance on __version__)
RUN python - <<'PY'
import sys, platform
from importlib.metadata import version, PackageNotFoundError
print("python:", sys.version)
try:
    print("playwright:", version("playwright"))
except PackageNotFoundError:
    print("playwright: MISSING")
    raise SystemExit(1)
PY

COPY . .
EXPOSE 8000
CMD ["bash", "-lc", "./start.sh"]
