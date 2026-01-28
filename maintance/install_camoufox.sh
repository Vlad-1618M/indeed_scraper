#!/bin/bash
# =============================================================================
# Indeed Scraper - Installation Script
# Installs Camoufox anti-detect browser and dependencies
# =============================================================================

set -e  # Exit on error

echo "=============================================="
echo "Indeed Scraper - Installation"
echo "=============================================="

# Install Python dependencies
echo ""
echo "[1/4] Installing Python dependencies..."
pip install --upgrade pip
pip install --upgrade certifi
# pip install -U "camoufox[geoip]"
pip install "camoufox==0.4.10"
pip install playwright

# Fix SSL certificates (required for macOS)
echo ""
echo "[2/4] Configuring SSL certificates..."
export SSL_CERT_FILE=$(python3 -c "import certifi; print(certifi.where())")
export REQUESTS_CA_BUNDLE=$(python3 -c "import certifi; print(certifi.where())")

echo "    SSL_CERT_FILE: $SSL_CERT_FILE"
echo "    REQUESTS_CA_BUNDLE: $REQUESTS_CA_BUNDLE"

# Download Camoufox browser
echo ""
echo "[3/4] Downloading Camoufox browser..."
camoufox fetch

# Verify installation
echo ""
echo "[4/4] Verifying installation..."
python3 -c "from camoufox.sync_api import Camoufox; print('[+] Camoufox imported successfully')"

echo ""
echo "=============================================="
echo "Installation complete!"
echo "=============================================="
echo ""
echo "Usage:"
echo "  Interactive:  python main.py"
echo "  Auto mode:    python main.py --auto --query \"DevOps Engineer\" --remote"
echo ""
echo "If you encounter SSL errors, add these to your shell profile (.zshrc or .bashrc):"
echo "  export SSL_CERT_FILE=\$(python3 -c \"import certifi; print(certifi.where())\")"
echo "  export REQUESTS_CA_BUNDLE=\$(python3 -c \"import certifi; print(certifi.where())\")"
echo ""
