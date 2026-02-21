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
echo "[2/6] Installing Python 3.13 and ffmpeg..."
# Pin to 3.13 - sounddevice/PortAudio crashes on 3.14 (GIL threading bug)
brew install python@3.13 ffmpeg 2>/dev/null || brew upgrade python@3.13 ffmpeg 2>/dev/null || true

# ── Step 3: Find the right Python (arm64, 3.11-3.13) ─────────────
echo "[3/6] Finding Python 3.11-3.13..."
PYTHON=""
BREW_PREFIX="$(brew --prefix)"

# Prefer 3.13, skip 3.14 (sounddevice/PortAudio GIL crash)
for candidate in \
    "$BREW_PREFIX/bin/python3.13" \
    "$BREW_PREFIX/bin/python3.12" \
    "$BREW_PREFIX/bin/python3.11" \
    "$BREW_PREFIX/bin/python3"; do

    if [ ! -x "$candidate" ]; then
        continue
    fi

    # Check version >= 3.11 and <= 3.13
    ver=$("$candidate" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null) || continue
    minor=$(echo "$ver" | cut -d. -f2)
    if [ "$minor" -lt 11 ] 2>/dev/null; then
        continue
    fi
    if [ "$minor" -ge 14 ] 2>/dev/null; then
        echo "  Skipping $candidate ($ver - sounddevice incompatible with 3.14+)"
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
    echo "  Need: Python 3.11-3.13 (arm64) from Homebrew"
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
echo "[4/6] Creating virtual environment..."
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
