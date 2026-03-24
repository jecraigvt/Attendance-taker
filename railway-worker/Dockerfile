# Use Microsoft's official Playwright Python image with all browser system libraries pre-installed.
# This avoids the most common Playwright-in-Docker failure: missing Chromium shared libraries.
FROM mcr.microsoft.com/playwright/python:v1.49.1-noble

WORKDIR /app

# Install Python dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Explicitly install the correct Chromium version for the installed playwright package.
# This ensures the browser stays in sync even if the base image drifts.
RUN playwright install chromium

# Copy all Python source files
COPY *.py .

# Copy selectors.json (not matched by *.py glob — required by sync_engine.py at import)
COPY selectors.json .

# Unbuffered output so Railway logs appear in real time (no Python output buffering)
ENV PYTHONUNBUFFERED=1

# worker.py is created in Plan 07-02 and runs the scheduled sync loop.
# For smoke testing, run: python smoke_test.py
CMD ["python", "worker.py"]
