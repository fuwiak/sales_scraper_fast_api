# Playwright Python base with browsers (v1.54)
FROM mcr.microsoft.com/playwright/python:v1.54.0-jammy

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# Install your Python deps (now includes playwright==1.54.0)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Optional smoke check (now should succeed)
RUN python - <<'PY'
import sys, playwright
print("python:", sys.version)
print("playwright:", playwright.__version__)
PY

# App files
COPY . .
EXPOSE 8000

# One worker reusing one Chromium instance
CMD ["bash", "-lc", "./start.sh"]
