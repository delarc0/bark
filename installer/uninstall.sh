#!/bin/bash
# Bark uninstaller - removes Bark from this Mac.
# Run: /usr/local/lib/bark/uninstall.sh

echo ""
echo "  Removing Bark..."

# Remove /Applications symlink or app
if [ -L "/Applications/Bark.app" ]; then
    rm -f "/Applications/Bark.app"
    echo "  Removed /Applications/Bark.app symlink"
elif [ -d "/Applications/Bark.app" ]; then
    rm -rf "/Applications/Bark.app"
    echo "  Removed /Applications/Bark.app"
fi

# Remove installation directory
if [ -d "/usr/local/lib/bark" ]; then
    rm -rf "/usr/local/lib/bark"
    echo "  Removed /usr/local/lib/bark"
fi

# Forget the package receipt
pkgutil --forget se.lab37.bark 2>/dev/null || true

echo ""
echo "  Bark has been removed."
echo "  Note: Homebrew, Python, and ffmpeg were NOT removed (other apps may use them)."
echo "  Note: Whisper model cache (~1.5 GB) is in ~/.cache/huggingface/ if you want to delete it."
echo ""
