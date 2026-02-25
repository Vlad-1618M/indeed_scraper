#!/usr/bin/env bash

# __ Selenium WebDriver Download Script for macOS: | for older selenium versions or just in case:

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DRIVERS_DIR="${SCRIPT_DIR}/drivers"

echo "drivers mkdir..."
mkdir -p "${DRIVERS_DIR}"

# __ Detect macOS architecture:
ARCH=$(uname -m)
if [[ "${ARCH}" == "arm64" ]]; then
    CHROME_ARCH="mac-arm64"
    FIREFOX_ARCH="macos-aarch64"
    echo "Detected: Apple Silicon (M1/M2/M3)"
else
    CHROME_ARCH="mac-x64"
    FIREFOX_ARCH="macos"
    echo "Detected: Intel Mac"
fi

# ============================================================================
#                   *** ChromeDriver download: *** 
# ============================================================================
echo ""
echo "================================================"
echo "Downloading ChromeDriver..."
echo "================================================"

# __ Get latest stable Chrome version:
CHROME_VERSION=$(curl -s "https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_STABLE")
echo "Latest Chrome version: ${CHROME_VERSION}"

# __ Download URL:
CHROMEDRIVER_URL="https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/${CHROME_ARCH}/chromedriver-${CHROME_ARCH}.zip"

echo "Downloading from: ${CHROMEDRIVER_URL}"
curl -L -o "${DRIVERS_DIR}/chromedriver.zip" "${CHROMEDRIVER_URL}"

# __ Extract:
echo "Extracting ChromeDriver..."
unzip -o "${DRIVERS_DIR}/chromedriver.zip" -d "${DRIVERS_DIR}/"
mv "${DRIVERS_DIR}/chromedriver-${CHROME_ARCH}/chromedriver" "${DRIVERS_DIR}/chromedriver"
rm -rf "${DRIVERS_DIR}/chromedriver-${CHROME_ARCH}"
rm "${DRIVERS_DIR}/chromedriver.zip"

# __ Make executable:
chmod +x "${DRIVERS_DIR}/chromedriver"

# __ Remove quarantine attribute (macOS Gatekeeper):
echo "Removing macOS quarantine attribute..."
xattr -d com.apple.quarantine "${DRIVERS_DIR}/chromedriver" 2>/dev/null || true

echo "✓ ChromeDriver installed: ${DRIVERS_DIR}/chromedriver"

# __ Verify:
"${DRIVERS_DIR}/chromedriver" --version

# ============================================================================
#                   *** GeckoDriver (Firefox) download: *** 
# ============================================================================
echo ""
echo "================================================"
echo "Downloading GeckoDriver (Firefox)..."
echo "================================================"

# __ Get latest GeckoDriver version:
GECKO_VERSION=$(curl -s "https://api.github.com/repos/mozilla/geckodriver/releases/latest" | grep '"tag_name":' | sed -E 's/.*"v([^"]+)".*/\1/')
echo "Latest GeckoDriver version: ${GECKO_VERSION}"

# __ Download URL:
GECKODRIVER_URL="https://github.com/mozilla/geckodriver/releases/download/v${GECKO_VERSION}/geckodriver-v${GECKO_VERSION}-${FIREFOX_ARCH}.tar.gz"

echo "Downloading from: ${GECKODRIVER_URL}"
curl -L -o "${DRIVERS_DIR}/geckodriver.tar.gz" "${GECKODRIVER_URL}"

# __ Extract:
echo "Extracting GeckoDriver..."
tar -xzf "${DRIVERS_DIR}/geckodriver.tar.gz" -C "${DRIVERS_DIR}/"
rm "${DRIVERS_DIR}/geckodriver.tar.gz"

# __ Make executable:
chmod +x "${DRIVERS_DIR}/geckodriver"

# __ Remove quarantine attribute (macOS Gatekeeper):
echo "Removing macOS quarantine attribute..."
xattr -d com.apple.quarantine "${DRIVERS_DIR}/geckodriver" 2>/dev/null || true

echo "✓ GeckoDriver installed: ${DRIVERS_DIR}/geckodriver"

# __ Verify:
"${DRIVERS_DIR}/geckodriver" --version

# ============================================================================
echo ""
echo "================================================"
echo "Installation complete!"
echo "================================================"
echo "ChromeDriver: ${DRIVERS_DIR}/chromedriver"
echo "GeckoDriver:  ${DRIVERS_DIR}/geckodriver"
echo "================================================"
echo ""
echo "Add to your PATH (optional):"
echo "export PATH=\"${DRIVERS_DIR}:\$PATH\""
echo "================================================"