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
    echo "[1/7] Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Add Homebrew to PATH for this session
    eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null || /usr/local/bin/brew shellenv 2>/dev/null)"
else
    echo "[1/7] Homebrew found."
fi

# ── Step 2: System dependencies ───────────────────────────────────
echo "[2/7] Installing Python and ffmpeg..."
brew install python ffmpeg 2>/dev/null || brew upgrade python ffmpeg 2>/dev/null || true

# ── Step 3: Find the right Python (arm64, 3.11+) ─────────────────
echo "[3/7] Finding Python 3.11+..."
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
    echo "  Try:  brew install python@3.13"
    echo ""
    exit 1
fi

echo "  Using: $PYTHON ($($PYTHON --version))"

# Install python-tk for tkinter support (Homebrew Python doesn't include it)
PY_MINOR=$(echo "$ver" | cut -d. -f2)
TK_FORMULA="python-tk@3.${PY_MINOR}"
echo "  Installing $TK_FORMULA (tkinter)..."
brew install "$TK_FORMULA" 2>/dev/null || brew install python-tk 2>/dev/null || true

# ── Step 4: Create virtual environment ────────────────────────────
echo "[4/7] Checking virtual environment..."

VENV_OK=0
if [ -f ".venv/bin/python3" ]; then
    VENV_PYTHON="$(pwd)/.venv/bin/python3"
    VENV_VER=$("$VENV_PYTHON" --version 2>&1) || VENV_VER=""
    VENV_MINOR=$("$VENV_PYTHON" -c 'import sys; print(sys.version_info.minor)' 2>&1) || VENV_MINOR=0
    VENV_ARCH=$(file "$VENV_PYTHON" 2>/dev/null | grep -o 'arm64\|x86_64' | head -1)
    if [ "$VENV_MINOR" -ge 11 ] 2>/dev/null; then
        if [ "$(uname -m)" != "arm64" ] || [ "$VENV_ARCH" = "arm64" ]; then
            VENV_OK=1
        fi
    fi
fi

if [ "$VENV_OK" = "1" ]; then
    echo "  Existing venv OK - reusing. ($VENV_VER, $VENV_ARCH)"
    source .venv/bin/activate
else
    echo "  Creating virtual environment..."
    rm -rf .venv
    "$PYTHON" -m venv .venv
    source .venv/bin/activate

    # Verify the venv Python is correct version and architecture
    VENV_PYTHON="$(pwd)/.venv/bin/python3"
    VENV_VER=$("$VENV_PYTHON" --version 2>&1)
    VENV_MINOR=$("$VENV_PYTHON" -c 'import sys; print(sys.version_info.minor)' 2>&1)
    VENV_ARCH=$(file "$VENV_PYTHON" 2>/dev/null | grep -o 'arm64\|x86_64' | head -1)
    echo "  venv Python: $VENV_VER ($VENV_ARCH)"

    if [ "$VENV_MINOR" -lt 11 ] 2>/dev/null; then
        echo ""
        echo "ERROR: venv created with Python $VENV_VER (need 3.11+)"
        echo "  This usually means the wrong Python was used."
        echo "  Delete .venv and install Homebrew Python:"
        echo "    rm -rf .venv"
        echo "    brew install python@3.12"
        echo "    ./setup-mac.sh"
        echo ""
        exit 1
    fi

    if [ "$(uname -m)" = "arm64" ] && [ "$VENV_ARCH" = "x86_64" ]; then
        echo ""
        echo "ERROR: venv Python is x86_64 on arm64 Mac."
        echo "  This will crash when loading arm64 wheels."
        echo "  Delete .venv and use Homebrew Python:"
        echo "    rm -rf .venv"
        echo "    brew install python@3.12"
        echo "    ./setup-mac.sh"
        echo ""
        exit 1
    fi
fi

# ── Step 5: Install dependencies ──────────────────────────────────
echo "[5/7] Installing dependencies (this may take a few minutes)..."
pip install --upgrade pip --quiet
pip install -r requirements-mac.txt --quiet

echo "  Dependencies installed."

# ── Step 6: Build Bark.app ────────────────────────────────────────
echo "[6/7] Building Bark.app..."
chmod +x create-app.sh
./create-app.sh

# ── Step 7: Add to Applications ──────────────────────────────────
echo "[7/7] Adding to Applications..."
BARK_APP="$(pwd)/Bark.app"
if [ -d "$BARK_APP" ]; then
    # Remove existing symlink or app
    if [ -L "/Applications/Bark.app" ]; then
        rm -f "/Applications/Bark.app"
    elif [ -d "/Applications/Bark.app" ]; then
        rm -rf "/Applications/Bark.app"
    fi
    # Symlink to /Applications (shows in Spotlight + Launchpad)
    ln -s "$BARK_APP" "/Applications/Bark.app" 2>/dev/null && \
        echo "  Bark.app added to /Applications" || \
        echo "  Could not symlink to /Applications (launch from $(pwd)/Bark.app instead)"
fi

echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║   Setup complete!                        ║"
echo "  ║                                          ║"
echo "  ║   Bark.app is in your Applications.      ║"
echo "  ║   Double-click it, or drag to Dock.      ║"
echo "  ║                                          ║"
echo "  ║   First launch:                          ║"
echo "  ║   - Grant Microphone permission          ║"
echo "  ║   - Grant Accessibility permission       ║"
echo "  ║   - Model downloads (~1.5 GB, once)      ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""
