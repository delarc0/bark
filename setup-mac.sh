#!/bin/bash
# Bark - One-command Mac setup
# Run: ./setup-mac.sh
# Handles everything: Homebrew, Python, dependencies, app bundle.

set -e
cd "$(dirname "$0")"

echo ""
echo "  ╔══════════════════════════╗"
echo "  ║   Bark - Mac Setup       ║"
echo "  ╚══════════════════════════╝"
echo ""

# ── Step 1: Homebrew ──────────────────────────────────────────────
if ! command -v brew &>/dev/null; then
    echo "[1/6] Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Add Homebrew to PATH for this session
    eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null || /usr/local/bin/brew shellenv 2>/dev/null)"
else
    echo "[1/6] Homebrew found."
fi

# ── Step 2: System dependencies ───────────────────────────────────
echo "[2/6] Installing Python and ffmpeg..."
brew install python ffmpeg 2>/dev/null || brew upgrade python ffmpeg 2>/dev/null || true

# ── Step 3: Find the right Python (arm64, 3.11+) ─────────────────
echo "[3/6] Finding Python 3.11+..."
PYTHON=""
BREW_PREFIX="$(brew --prefix)"

# Try versioned Homebrew Pythons first (most specific), then generic
for candidate in \
    "$BREW_PREFIX/bin/python3.14" \
    "$BREW_PREFIX/bin/python3.13" \
    "$BREW_PREFIX/bin/python3.12" \
    "$BREW_PREFIX/bin/python3.11" \
    "$BREW_PREFIX/bin/python3"; do

    if [ ! -x "$candidate" ]; then
        continue
    fi

    # Check version >= 3.11
    ver=$("$candidate" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null) || continue
    minor=$(echo "$ver" | cut -d. -f2)
    if [ "$minor" -lt 11 ] 2>/dev/null; then
        continue
    fi

    # Check architecture (must be arm64 on Apple Silicon)
    arch=$(file "$candidate" 2>/dev/null | grep -o 'arm64\|x86_64' | head -1)
    if [ "$(uname -m)" = "arm64" ] && [ "$arch" = "x86_64" ]; then
        echo "  Skipping $candidate (x86_64 binary on arm64 Mac)"
        continue
    fi

    PYTHON="$candidate"
    break
done

if [ -z "$PYTHON" ]; then
    echo ""
    echo "ERROR: No suitable Python found."
    echo "  Need: Python 3.11+ (arm64) from Homebrew"
    echo "  Try:  brew install python@3.12"
    echo ""
    exit 1
fi

echo "  Using: $PYTHON ($($PYTHON --version))"

# ── Step 4: Create virtual environment ────────────────────────────
echo "[4/6] Creating virtual environment..."
rm -rf .venv
"$PYTHON" -m venv .venv
source .venv/bin/activate

# Verify the venv Python is correct
VENV_VER=$(python3 --version 2>&1)
echo "  venv Python: $VENV_VER"

# ── Step 5: Install dependencies ──────────────────────────────────
echo "[5/6] Installing dependencies (this may take a few minutes)..."
pip install --upgrade pip --quiet
pip install -r requirements-mac.txt --quiet

echo "  Dependencies installed."

# ── Step 6: Build Bark.app ────────────────────────────────────────
echo "[6/6] Building Bark.app..."
chmod +x create-app.sh
./create-app.sh

echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║   Setup complete!                        ║"
echo "  ║                                          ║"
echo "  ║   Double-click Bark.app to launch.       ║"
echo "  ║   Or drag it to your Dock.               ║"
echo "  ║                                          ║"
echo "  ║   First launch:                          ║"
echo "  ║   - Grant Microphone permission          ║"
echo "  ║   - Grant Accessibility permission       ║"
echo "  ║   - Model downloads (~1.5 GB, once)      ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""
