#!/bin/bash
# build-installer.sh - Creates Bark-Installer.pkg for macOS
# Run on macOS: ./installer/build-installer.sh
# Output: installer/build/Bark-Installer.pkg

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BUILD_DIR="$SCRIPT_DIR/build"
PAYLOAD_DIR="$BUILD_DIR/payload"
INSTALL_ROOT="$PAYLOAD_DIR/usr/local/lib/bark"

PKG_ID="se.lab37.bark"
PKG_VERSION="1.0.0"

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║   Building Bark Installer (.pkg)     ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

# Must run on macOS (pkgbuild is macOS-only)
if [ "$(uname)" != "Darwin" ]; then
    echo "ERROR: This script must be run on macOS."
    exit 1
fi

# Clean previous build
rm -rf "$BUILD_DIR"
mkdir -p "$INSTALL_ROOT"

# ── Stage source files ────────────────────────────────────────────
echo "[1/3] Staging source files..."

SOURCE_FILES=(
    dictation.py
    audio.py
    transcriber.py
    keyboard_hook.py
    overlay.py
    feedback.py
    config.py
    icon.ico
    requirements-mac.txt
    setup-mac.sh
    create-app.sh
    start.sh
)

for f in "${SOURCE_FILES[@]}"; do
    if [ -f "$PROJECT_DIR/$f" ]; then
        cp "$PROJECT_DIR/$f" "$INSTALL_ROOT/$f"
    else
        echo "  WARNING: $f not found, skipping"
    fi
done

chmod +x "$INSTALL_ROOT/setup-mac.sh"
chmod +x "$INSTALL_ROOT/create-app.sh"
chmod +x "$INSTALL_ROOT/start.sh"

# Include uninstall script
cp "$SCRIPT_DIR/uninstall.sh" "$INSTALL_ROOT/uninstall.sh"
chmod +x "$INSTALL_ROOT/uninstall.sh"

FILE_COUNT=$(ls -1 "$INSTALL_ROOT" | wc -l | tr -d ' ')
echo "  Staged $FILE_COUNT files."

# ── Copy installer scripts ───────────────────────────────────────
echo "[2/3] Preparing installer scripts..."

mkdir -p "$BUILD_DIR/scripts"
cp "$SCRIPT_DIR/scripts/preinstall" "$BUILD_DIR/scripts/preinstall"
cp "$SCRIPT_DIR/scripts/postinstall" "$BUILD_DIR/scripts/postinstall"
chmod +x "$BUILD_DIR/scripts/preinstall"
chmod +x "$BUILD_DIR/scripts/postinstall"

# ── Build .pkg ────────────────────────────────────────────────────
echo "[3/3] Building package..."

pkgbuild \
    --root "$PAYLOAD_DIR" \
    --scripts "$BUILD_DIR/scripts" \
    --identifier "$PKG_ID" \
    --version "$PKG_VERSION" \
    --install-location "/" \
    "$BUILD_DIR/Bark-Installer.pkg"

PKG_SIZE=$(du -sh "$BUILD_DIR/Bark-Installer.pkg" | cut -f1)

echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║   Package built successfully!            ║"
echo "  ║                                          ║"
echo "  ║   $BUILD_DIR/Bark-Installer.pkg"
echo "  ║   Size: $PKG_SIZE"
echo "  ║                                          ║"
echo "  ║   Distribute this .pkg to users.         ║"
echo "  ║   They double-click to install.          ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""
