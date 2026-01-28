#!/bin/bash
# =============================================================================
# Camoufox Cleanup Script
# Completely removes Camoufox and reinstalls a specific version
# =============================================================================

set -e

# Default version to install (can be overridden via argument)
CAMOUFOX_VERSION="${1:-0.4.10}"

echo "=============================================="
echo "Camoufox Cleanup & Reinstall"
echo "Target version: $CAMOUFOX_VERSION"
echo "=============================================="

# Detect OS
OS="$(uname -s)"
echo "[*] Detected OS: $OS"

# Step 1: Uninstall pip packages
echo ""
echo "[1/6] Uninstalling pip packages..."
pip uninstall camoufox browserforge -y 2>/dev/null || echo "    Packages not installed or already removed"

# Step 2: Remove cached browser (OS-specific paths)
echo ""
echo "[2/6] Removing cached browser files..."

if [ "$OS" = "Darwin" ]; then
    # macOS paths
    echo "    Cleaning macOS paths..."
    rm -rf ~/Library/Caches/camoufox 2>/dev/null && echo "    Removed ~/Library/Caches/camoufox" || true
    rm -f ~/Library/Preferences/org.mozilla.camoufox.plist 2>/dev/null && echo "    Removed camoufox preferences" || true
    rm -rf ~/Library/Application\ Support/camoufox 2>/dev/null && echo "    Removed ~/Library/Application Support/camoufox" || true
elif [ "$OS" = "Linux" ]; then
    # Linux paths
    echo "    Cleaning Linux paths..."
    rm -rf ~/.camoufox 2>/dev/null && echo "    Removed ~/.camoufox" || true
    rm -rf ~/.cache/camoufox 2>/dev/null && echo "    Removed ~/.cache/camoufox" || true
    rm -rf ~/.local/share/camoufox 2>/dev/null && echo "    Removed ~/.local/share/camoufox" || true
else
    # Windows (Git Bash / WSL)
    echo "    Cleaning Windows paths..."
    rm -rf "$LOCALAPPDATA/camoufox" 2>/dev/null || true
    rm -rf "$APPDATA/camoufox" 2>/dev/null || true
fi

# Step 3: Remove from Python site-packages
echo ""
echo "[3/6] Cleaning Python site-packages..."
PYTHON_SITE=$(python3 -c "import site; print(site.getsitepackages()[0])" 2>/dev/null || echo "")
if [ -n "$PYTHON_SITE" ] && [ -d "$PYTHON_SITE/camoufox" ]; then
    rm -rf "$PYTHON_SITE/camoufox" && echo "    Removed $PYTHON_SITE/camoufox"
fi
if [ -n "$PYTHON_SITE" ] && [ -d "$PYTHON_SITE/browserforge" ]; then
    rm -rf "$PYTHON_SITE/browserforge" && echo "    Removed $PYTHON_SITE/browserforge"
fi

# Step 4: Clear pip cache
echo ""
echo "[4/6] Clearing pip cache for camoufox..."
pip cache remove camoufox 2>/dev/null || true
pip cache remove browserforge 2>/dev/null || true

# # Step 5: Reinstall specific version
# echo ""
# echo "[5/6] Installing camoufox==$CAMOUFOX_VERSION..."
# pip install "camoufox==$CAMOUFOX_VERSION"

# # Step 6: Fetch browser
# echo ""
# echo "[6/6] Fetching Camoufox browser..."
# camoufox fetch

# Verify
echo ""
echo "=============================================="
echo "Verification"
echo "=============================================="
camoufox version

echo ""
echo "=============================================="
echo "Cleanup complete!"
echo "=============================================="
echo ""
echo "If font issues persist, the beta browser may still be"
echo "served by the fetch server. In that case, consider:"
echo "  1. SeleniumBase UC Mode: pip install seleniumbase"
echo "  2. Plain Playwright with stealth patches"
echo ""
