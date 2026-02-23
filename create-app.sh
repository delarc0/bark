#!/bin/bash
# Creates Bark.app - a macOS application bundle for Bark dictation tool.
# Run this once after setup: ./create-app.sh
# Then double-click Bark.app in Finder, or drag it to your Dock.

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="Bark"
APP_DIR="$SCRIPT_DIR/$APP_NAME.app"

echo "Creating $APP_NAME.app..."

# Clean previous build
rm -rf "$APP_DIR"

# Create .app bundle structure
mkdir -p "$APP_DIR/Contents/MacOS"
mkdir -p "$APP_DIR/Contents/Resources"

# Launcher script - uses placeholder replaced with hardcoded path at build time
cat > "$APP_DIR/Contents/MacOS/bark" << 'LAUNCHER'
#!/bin/bash
DIR="__PROJECT_DIR__"
LOG="$DIR/dictation.log"
PYTHON="$DIR/.venv/bin/python3"

# Show error dialog (works even before log redirect)
show_error() {
    osascript -e "display alert \"Bark\" message \"$1\" as critical" 2>/dev/null
}

# Validate project dir BEFORE redirecting (if DIR is wrong, redirect fails silently)
if [ ! -d "$DIR" ]; then
    show_error "Project folder not found:\n$DIR\n\nRebuild with: ./create-app.sh"
    exit 1
fi

# Now safe to redirect to log
exec >> "$LOG" 2>&1

echo ""
echo "=== Bark launch $(date) ==="
echo "DIR: $DIR"

cd "$DIR" || {
    show_error "Could not cd to project folder."
    exit 1
}

if [ ! -f "$PYTHON" ]; then
    echo "ERROR: venv Python not found at $PYTHON"
    show_error "Virtual environment not found.\n\nRun: ./setup-mac.sh"
    exit 1
fi

# Verify Python version (need 3.11+ for mlx-whisper)
PYVER=$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>&1)
PYMINOR=$("$PYTHON" -c 'import sys; print(sys.version_info.minor)' 2>&1)
echo "Python: $PYTHON ($PYVER)"
echo "Arch: $(file "$PYTHON" | grep -o 'arm64\|x86_64')"

if [ "$PYMINOR" -lt 11 ] 2>/dev/null; then
    echo "ERROR: Python $PYVER is too old (need 3.11+)"
    show_error "Python $PYVER is too old. Need 3.11+.\n\nRe-run: ./setup-mac.sh"
    exit 1
fi

# Activate venv properly. Do NOT set PYTHONHOME -- it overrides pyvenv.cfg
# and prevents Python from finding its standard library, causing a silent
# fatal crash (no log output, no error dialog, just "nothing happens").
export VIRTUAL_ENV="$DIR/.venv"
export PATH="$DIR/.venv/bin:$PATH"
unset PYTHONHOME

# Tell macOS frameworks this process belongs to the Bark bundle
export __CFBundleIdentifier=se.lab37.bark

exec "$PYTHON" "$DIR/dictation.py"
LAUNCHER

# Inject absolute project path into launcher
sed -i '' "s|__PROJECT_DIR__|$SCRIPT_DIR|g" "$APP_DIR/Contents/MacOS/bark"
chmod +x "$APP_DIR/Contents/MacOS/bark"

# Read version from VERSION file (single source of truth)
APP_VERSION="1.0"
if [ -f "$SCRIPT_DIR/VERSION" ]; then
    APP_VERSION="$(cat "$SCRIPT_DIR/VERSION" | tr -d '[:space:]')"
fi

# Info.plist
cat > "$APP_DIR/Contents/Info.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>Bark</string>
    <key>CFBundleDisplayName</key>
    <string>Bark</string>
    <key>CFBundleIdentifier</key>
    <string>se.lab37.bark</string>
    <key>CFBundleVersion</key>
    <string>${APP_VERSION}</string>
    <key>CFBundleShortVersionString</key>
    <string>${APP_VERSION}</string>
    <key>CFBundleExecutable</key>
    <string>bark</string>
    <key>CFBundleIconFile</key>
    <string>bark</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSUIElement</key>
    <true/>
    <key>NSMicrophoneUsageDescription</key>
    <string>Bark needs microphone access for speech-to-text dictation.</string>
    <key>NSAppleEventsUsageDescription</key>
    <string>Bark needs Accessibility access to monitor keyboard input and paste transcribed text.</string>
</dict>
</plist>
PLIST

# Generate app icon from custom PNG (icon.png in project root)
ICONSET="$APP_DIR/Contents/Resources/bark.iconset"
ICON_SRC="$SCRIPT_DIR/icon.png"
mkdir -p "$ICONSET"

if [ ! -f "$ICON_SRC" ]; then
    echo "Warning: icon.png not found - app will have no icon."
else
    source "$SCRIPT_DIR/.venv/bin/activate" 2>/dev/null || true

    python3 -c "
from PIL import Image
import os, sys

src = Image.open('$ICON_SRC').convert('RGBA')
iconset = '$ICONSET'

sizes = [
    (16, '16x16'), (32, '16x16@2x'),
    (32, '32x32'), (64, '32x32@2x'),
    (128, '128x128'), (256, '128x128@2x'),
    (256, '256x256'), (512, '256x256@2x'),
    (512, '512x512'), (1024, '512x512@2x'),
]

for sz, name in sizes:
    resized = src.resize((sz, sz), Image.LANCZOS)
    resized.save(os.path.join(iconset, f'icon_{name}.png'))

print('Icon generated from icon.png')
"
fi

# Convert iconset to .icns
if command -v iconutil &>/dev/null; then
    iconutil -c icns "$ICONSET" -o "$APP_DIR/Contents/Resources/bark.icns" 2>/dev/null && rm -rf "$ICONSET"
    echo "Icon packed."
else
    rm -rf "$ICONSET"
    echo "Note: iconutil not found (run on Mac to generate .icns icon)."
fi

# Remove quarantine flag so macOS doesn't block the app
xattr -cr "$APP_DIR" 2>/dev/null || true

echo ""
echo "Done! $APP_NAME.app created at: $APP_DIR"
echo ""
echo "  Double-click in Finder, or drag to your Dock."
echo "  First launch: grant Accessibility + Microphone permissions."
