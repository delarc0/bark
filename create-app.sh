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

# Launcher script (the actual executable macOS runs)
cat > "$APP_DIR/Contents/MacOS/bark" << 'LAUNCHER'
#!/bin/bash
# Bark launcher - runs the Python dictation tool
DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$DIR"

# Log file for debugging launch issues
LOG="$DIR/dictation.log"

if [ ! -d "$DIR/.venv" ]; then
    osascript -e 'display alert "Bark" message "Virtual environment not found. Run setup first:\n\ncd '"$DIR"' && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements-mac.txt" as warning'
    exit 1
fi

source "$DIR/.venv/bin/activate"
exec python "$DIR/dictation.py" >> "$LOG" 2>&1
LAUNCHER
chmod +x "$APP_DIR/Contents/MacOS/bark"

# Info.plist (required for macOS to treat this as a real app)
cat > "$APP_DIR/Contents/Info.plist" << 'PLIST'
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
    <string>1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
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

# Create a simple .icns icon from the green Bark logo
# Uses built-in macOS sips + iconutil (no dependencies)
ICONSET="$APP_DIR/Contents/Resources/bark.iconset"
mkdir -p "$ICONSET"

# Generate a simple green terminal icon using Python (available since we have the venv)
source "$DIR/.venv/bin/activate" 2>/dev/null || true
python3 -c "
import struct, zlib

def create_png(size):
    \"\"\"Create a minimal green-on-black icon PNG.\"\"\"
    pad = size // 8
    bar_h = size // 5
    rows = []
    for y in range(size):
        row = bytearray()
        for x in range(size):
            in_border = x < pad or x >= size - pad or y < pad or y >= size - pad
            in_bar = (pad * 2 <= x < size - pad * 2) and (size // 2 - bar_h // 2 <= y < size // 2 + bar_h // 2)
            if in_border and not (x >= pad and x < size - pad and y >= pad and y < size - pad):
                row.extend([0x42, 0xFC, 0x93, 255])  # Green border
            elif in_bar:
                row.extend([0x42, 0xFC, 0x93, 255])  # Green bar
            else:
                row.extend([0x11, 0x11, 0x13, 255])  # Dark surface
        rows.append(bytes([0]) + bytes(row))  # Filter byte + row

    raw = b''.join(rows)

    def chunk(ctype, data):
        c = ctype + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF)

    ihdr = struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0)
    return b'\\x89PNG\\r\\n\\x1a\\n' + chunk(b'IHDR', ihdr) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')

for size, name in [(16,'16x16'), (32,'16x16@2x'), (32,'32x32'), (64,'32x32@2x'), (128,'128x128'), (256,'128x128@2x'), (256,'256x256'), (512,'256x256@2x'), (512,'512x512'), (1024,'512x512@2x')]:
    with open('$ICONSET/icon_' + name + '.png', 'wb') as f:
        f.write(create_png(size))
print('Icon PNGs generated.')
" 2>/dev/null

# Convert iconset to .icns (macOS built-in tool)
if command -v iconutil &>/dev/null; then
    iconutil -c icns "$ICONSET" -o "$APP_DIR/Contents/Resources/bark.icns" 2>/dev/null && rm -rf "$ICONSET"
    echo "Icon created."
else
    rm -rf "$ICONSET"
    echo "Note: iconutil not found (run on Mac to generate icon)."
fi

echo ""
echo "Done! $APP_NAME.app created."
echo ""
echo "To use:"
echo "  1. Double-click Bark.app in Finder"
echo "  2. Or drag it to your Dock for quick access"
echo ""
echo "First launch: macOS will ask for Accessibility + Microphone permissions."
echo "Grant both in System Settings > Privacy & Security."
