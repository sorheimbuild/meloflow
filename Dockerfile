FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    curl \
    unzip \
    ffmpeg \
    chromium \
    chromium-sandbox \
    && rm -rf /var/lib/apt/lists/*

# Set Chrome as default browser
ENV CHROME_BIN=/usr/bin/chromium

# Install Python dependencies
COPY requirements-docker.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements-docker.txt

# Install selenium for cookie extraction
RUN pip install --no-cache-dir selenium undetected-chromedriver

# Install Playwright browsers
RUN playwright install chromium && playwright install-deps chromium

# Copy application
WORKDIR /app
COPY . /app/

# Create downloads directory
RUN mkdir -p /downloads /root/.lucida-flow

# Run the downloader
CMD ["python", "-m", "cli", "download-docker"]
