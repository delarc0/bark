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

cd "$DIR" || {
    osascript -e 'display alert "Bark" message "Project folder not found.\n\nRebuild: cd /path/to/bark && ./create-app.sh" as critical'
    exit 1
}

if [ ! -d "$DIR/.venv" ]; then
    osascript -e 'display alert "Bark" message "Virtual environment not found.\n\nRun setup:\ncd '"$DIR"'\npython3 -m venv .venv && source .venv/bin/activate\npip install -r requirements-mac.txt\n./create-app.sh" as warning'
    exit 1
fi

source "$DIR/.venv/bin/activate"

python "$DIR/dictation.py" >> "$LOG" 2>&1 || {
    LAST_ERR=$(tail -5 "$LOG" 2>/dev/null)
    osascript -e "display alert \"Bark failed to start\" message \"Check $LOG for details.\n\n$LAST_ERR\" as critical"
    exit 1
}
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
ICONSET="$APP_DIR/Contents/Resources/bark.iconset"
mkdir -p "$ICONSET"

source "$SCRIPT_DIR/.venv/bin/activate" 2>/dev/null || true

ICONSET="$ICONSET" python3 -c "
import struct, zlib, math, os

GREEN = (0x42, 0xFC, 0x93)
GREEN_DIM = (0x1a, 0x6b, 0x3d)
BG = (0x0d, 0x0d, 0x0f)

def lerp(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))

def dist(x1, y1, x2, y2):
    return math.sqrt((x1 - x2)**2 + (y1 - y2)**2)

def create_icon(size):
    cx, cy = size / 2, size / 2
    margin = size * 0.08
    corner_r = size * 0.18
    bar_heights = [0.30, 0.55, 1.0, 0.70, 0.40]
    num_bars = len(bar_heights)
    bar_w = size * 0.09
    bar_gap = size * 0.05
    total_w = num_bars * bar_w + (num_bars - 1) * bar_gap
    bars_x_start = (size - total_w) / 2
    max_bar_h = size * 0.50

    rows = []
    for y in range(size):
        row = bytearray()
        for x in range(size):
            in_rect = (margin <= x < size - margin) and (margin <= y < size - margin)
            if in_rect:
                lx, rx = margin + corner_r, size - margin - corner_r
                ty, by = margin + corner_r, size - margin - corner_r
                in_corner = False
                if x < lx and y < ty: in_corner = dist(x, y, lx, ty) > corner_r
                elif x > rx and y < ty: in_corner = dist(x, y, rx, ty) > corner_r
                elif x < lx and y > by: in_corner = dist(x, y, lx, by) > corner_r
                elif x > rx and y > by: in_corner = dist(x, y, rx, by) > corner_r
                if in_corner: in_rect = False

            if not in_rect:
                row.extend([0, 0, 0, 0])
                continue

            r, g, b = BG
            in_bar = False
            glow_intensity = 0.0

            for i, bh in enumerate(bar_heights):
                bx = bars_x_start + i * (bar_w + bar_gap)
                bar_h = bh * max_bar_h
                bar_top, bar_bot = cy - bar_h / 2, cy + bar_h / 2
                bar_cx = bx + bar_w / 2

                if bx <= x < bx + bar_w and bar_top <= y <= bar_bot:
                    in_bar = True
                    dx = abs(x - bar_cx) / (bar_w / 2)
                    dy = abs(y - cy) / (bar_h / 2)
                    edge = max(dx, dy * 0.3)
                    r, g, b = lerp(GREEN, GREEN_DIM, edge * 0.6)
                    break

                # Glow halo around each bar
                d = 0.0
                if bx <= x < bx + bar_w:
                    d = max(0, bar_top - y) if y < bar_top else max(0, y - bar_bot)
                elif bar_top <= y <= bar_bot:
                    d = max(0, bx - x) if x < bx else max(0, x - (bx + bar_w))
                else:
                    corners = [(bx, bar_top), (bx + bar_w, bar_top), (bx, bar_bot), (bx + bar_w, bar_bot)]
                    d = min(dist(x, y, cx2, cy2) for cx2, cy2 in corners)
                glow_r = size * 0.06
                if d < glow_r:
                    gi = (1.0 - d / glow_r) * 0.35 * bh
                    glow_intensity = max(glow_intensity, gi)

            if not in_bar and glow_intensity > 0:
                r, g, b = lerp(BG, GREEN_DIM, glow_intensity)

            # Subtle scanlines
            if y % 4 == 0:
                r, g, b = int(r * 0.85), int(g * 0.85), int(b * 0.85)

            row.extend([r, g, b, 255])
        rows.append(bytes([0]) + bytes(row))

    raw = b''.join(rows)
    def chunk(ct, data):
        c = ct + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF)
    ihdr = struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b'')

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
