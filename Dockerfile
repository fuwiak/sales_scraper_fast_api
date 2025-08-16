# Playwright Python + browsers preinstalled (version 1.54)
FROM mcr.microsoft.com/playwright/python:v1.54.0-jammy

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# Install only your app deps (NOT playwright)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Smoke check: fail build if Playwright isn't present (it should be)
RUN python - <<'PY'
import playwright, sys
print("python:", sys.version)
print("playwright:", playwright.__version__)
PY

COPY . .
EXPOSE 8000
CMD ["bash", "-lc", "./start.sh"]
