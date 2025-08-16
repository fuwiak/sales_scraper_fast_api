# Use the official Playwright image (includes Chromium + deps)
FROM mcr.microsoft.com/playwright/python:v1.46.0-jammy

# System prep (faster, quieter installs)
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# Install Python deps first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . .

# Expose for Railway (it injects PORT at runtime)
EXPOSE 8000

# Start (single worker; we reuse one Chromium per process)
CMD ["bash", "-lc", "./start.sh"]
