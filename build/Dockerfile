# =============================================================================
#       *** Indeed Job Scraper - Docker Container ***
# =============================================================================
# Supports: ARM64 (Apple Silicon) + AMD64 (Intel/AMD)
# Scrapers: SeleniumBase UC Mode, Playwright, Camoufox
# =============================================================================

FROM python:3.11-slim-bookworm

LABEL maintainer="Indeed Scraper Project"
LABEL description="Indeed job scraper with Cloudflare bypass capabilities"

# =============================================================================
#                       *** SYSTEM DEPENDENCIES ***
# =============================================================================

# ___ Install Chromium, virtual display, and browser dependencies:
# ___ Using Chromium instead of Chrome for ARM64 compatibility:
RUN apt-get update && apt-get install -y --no-install-recommends \
    # ___ Core utilities:
    wget \
    curl \
    gnupg \
    unzip \
    ca-certificates \
    # ___ Chromium browser | <-- works on ARM64 + AMD64:
    chromium \
    chromium-driver \
    # ___ Virtual display for headless GUI operations | <-- required for UC Mode:
    xvfb \
    x11-utils \
    xauth \
    # ___ D-Bus for X11 compatibility | <-- fixes SeleniumBase display detection:
    dbus-x11 \
    # ___ Browser dependencies:
    fonts-liberation \
    fonts-noto-color-emoji \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    # ___ Firefox dependencies | <-- for Camoufox:
    libdbus-glib-1-2 \
    libxt6 \
    # ___ PyAutoGUI dependencies:
    python3-tk \
    python3-dev \
    scrot \
    && rm -rf /var/lib/apt/lists/*

# ___ Verify Chromium installation:
RUN chromium --version && chromedriver --version

# =============================================================================
#               *** ENVIRONMENT VARIABLES FOR CHROMIUM ***
# =============================================================================

# ___ Tell SeleniumBase/Selenium where to find Chromium:
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

# ___ Chromium flags for container environment:
ENV CHROMIUM_FLAGS="--no-sandbox --disable-dev-shm-usage --disable-gpu"

# =============================================================================
#                       *** PYTHON ENVIRONMENT ***
# =============================================================================

WORKDIR /app

# ___ Copy requirements first | <-- for Docker layer caching:
COPY requirements.txt .

# ___ Install Python dependencies:
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ___ Install Playwright browsers | <-- Optional, for Playwright scraper:
# ___ This will install the correct architecture automatically:
RUN playwright install chromium --with-deps || true

# =============================================================================
#                       *** APPLICATION CODE ***
# =============================================================================

# ___ Copy application modules:
COPY modules/ ./modules/
COPY src/ ./src/

# ___ Copy docs if they exist | <-- use wildcard to avoid failure if missing:
COPY doc[s]/ ./docs/

# ___ Create artifacts directories:
RUN mkdir -p artifacts/json artifacts/logs artifacts/screenshots/pages artifacts/screenshots/cards

# =============================================================================
#                   *** ENVIRONMENT CONFIGURATION ***
# =============================================================================

# ___ Python settings:
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# ___ Display settings | <-- xvfb-run will override with auto-selected display:
ENV DISPLAY=:99

# ___ SeleniumBase settings:
ENV SB_UC_MODE=true

# ___ Timezone | <-- override with -e TZ=your/timezone:
ENV TZ=UTC

# =============================================================================
#                           *** ENTRYPOINT ***
# =============================================================================

# ___ Copy entrypoint script:
COPY build/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

# ___ Default command | <-- shows help:
CMD ["python", "src/main.py", "--help"]
