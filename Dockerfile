# Match Playwright runtime & browsers (v1.54)
FROM mcr.microsoft.com/playwright/python:v1.54.0-jammy

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# Install only your app deps (do NOT install playwright here)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

EXPOSE 8000

# Single worker so one Chromium is reused per process
CMD ["bash", "-lc", "./start.sh"]
