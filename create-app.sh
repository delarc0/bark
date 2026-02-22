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

# exec replaces this shell with Python so macOS sees the .app bundle
# (not "Python") in permission dialogs and Dock
exec "$PYTHON" "$DIR/dictation.py"
LAUNCHER

# Inject absolute project path into launcher
sed -i '' "s|__PROJECT_DIR__|$SCRIPT_DIR|g" "$APP_DIR/Contents/MacOS/bark"
chmod +x "$APP_DIR/Contents/MacOS/bark"

# Info.plist
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

# Generate app icon - waveform bars in LAB37 green on dark background
# Uses numpy for fast vectorized rendering (no per-pixel Python loops)
ICONSET="$APP_DIR/Contents/Resources/bark.iconset"
mkdir -p "$ICONSET"

source "$SCRIPT_DIR/.venv/bin/activate" 2>/dev/null || true

ICONSET="$ICONSET" python3 -c "
import struct, zlib, os
import numpy as np

def create_icon(size):
    s = size
    img = np.zeros((s, s, 4), dtype=np.uint8)

    # Coordinate grids
    yy, xx = np.mgrid[0:s, 0:s].astype(np.float32)
    cx, cy = s / 2, s / 2

    # Rounded rect mask
    margin = s * 0.08
    corner_r = s * 0.18
    in_rect = (xx >= margin) & (xx < s - margin) & (yy >= margin) & (yy < s - margin)
    # Cut corners
    for (cxc, cyc) in [(margin + corner_r, margin + corner_r),
                        (s - margin - corner_r, margin + corner_r),
                        (margin + corner_r, s - margin - corner_r),
                        (s - margin - corner_r, s - margin - corner_r)]:
        corner_zone = ((xx < margin + corner_r) if cxc < cx else (xx > s - margin - corner_r)) & \
                      ((yy < margin + corner_r) if cyc < cy else (yy > s - margin - corner_r))
        dist = np.sqrt((xx - cxc)**2 + (yy - cyc)**2)
        in_rect = in_rect & ~(corner_zone & (dist > corner_r))

    # Dark background
    img[in_rect] = [0x0d, 0x0d, 0x0f, 255]

    # Scanlines
    scanline = (yy % 4 == 0) & in_rect
    img[scanline] = [0x0a, 0x0a, 0x0c, 255]

    # Waveform bars
    bar_heights = [0.30, 0.55, 1.0, 0.70, 0.40]
    bar_w = s * 0.09
    bar_gap = s * 0.05
    total_w = len(bar_heights) * bar_w + (len(bar_heights) - 1) * bar_gap
    x_start = (s - total_w) / 2
    max_h = s * 0.50

    for i, bh in enumerate(bar_heights):
        bx = x_start + i * (bar_w + bar_gap)
        bar_h = bh * max_h
        bar_top = cy - bar_h / 2
        bar_bot = cy + bar_h / 2

        bar_mask = (xx >= bx) & (xx < bx + bar_w) & (yy >= bar_top) & (yy <= bar_bot) & in_rect
        img[bar_mask] = [0x42, 0xFC, 0x93, 255]

        # Glow around bar
        glow_r = s * 0.04
        glow_zone = (xx >= bx - glow_r) & (xx < bx + bar_w + glow_r) & \
                    (yy >= bar_top - glow_r) & (yy <= bar_bot + glow_r) & \
                    in_rect & ~bar_mask
        if np.any(glow_zone):
            dx = np.maximum(0, np.maximum(bx - xx, xx - (bx + bar_w)))
            dy = np.maximum(0, np.maximum(bar_top - yy, yy - bar_bot))
            d = np.sqrt(dx**2 + dy**2)
            glow_mask = glow_zone & (d < glow_r)
            if np.any(glow_mask):
                t = (1.0 - d[glow_mask] / glow_r) * 0.4 * bh
                img[glow_mask, 0] = (0x0d + t * (0x1a - 0x0d)).astype(np.uint8)
                img[glow_mask, 1] = (0x0d + t * (0x6b - 0x0d)).astype(np.uint8)
                img[glow_mask, 2] = (0x0f + t * (0x3d - 0x0f)).astype(np.uint8)

    # Encode PNG
    raw = b''.join(bytes([0]) + row.tobytes() for row in img)
    def chunk(ct, data):
        c = ct + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF)
    ihdr = struct.pack('>IIBBBBB', s, s, 8, 6, 0, 0, 0)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')

iconset = os.environ['ICONSET']
for sz, name in [(16,'16x16'),(32,'16x16@2x'),(32,'32x32'),(64,'32x32@2x'),(128,'128x128'),(256,'128x128@2x'),(256,'256x256'),(512,'256x256@2x'),(512,'512x512'),(1024,'512x512@2x')]:
    with open(os.path.join(iconset, f'icon_{name}.png'), 'wb') as f:
        f.write(create_icon(sz))
print('Icon generated.')
"

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
