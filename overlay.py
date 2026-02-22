import logging
import math
import os
import tkinter as tk

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageTk

from config import cfg, save_config, IS_WIN, IS_MAC, TRIGGER_KEY_NAME

log = logging.getLogger(__name__)

# --- Windows setup ---
if IS_WIN:
    import ctypes
    import ctypes.wintypes as wt

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("lab37.bark")
    except Exception:
        pass

    # Win32 constants for layered window (per-pixel alpha)
    _GWL_EXSTYLE = -20
    _WS_EX_LAYERED = 0x00080000
    _ULW_ALPHA = 0x02
    _AC_SRC_OVER = 0x00
    _AC_SRC_ALPHA = 0x01

    class _BLENDFUNCTION(ctypes.Structure):
        _fields_ = [
            ("BlendOp", ctypes.c_byte),
            ("BlendFlags", ctypes.c_byte),
            ("SourceConstantAlpha", ctypes.c_byte),
            ("AlphaFormat", ctypes.c_byte),
        ]

    class _POINT(ctypes.Structure):
        _fields_ = [("x", wt.LONG), ("y", wt.LONG)]

    class _SIZE(ctypes.Structure):
        _fields_ = [("cx", wt.LONG), ("cy", wt.LONG)]

    class _BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
            ("biPlanes", wt.WORD), ("biBitCount", wt.WORD),
            ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
            ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG),
            ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD),
        ]

    class _BITMAPINFO(ctypes.Structure):
        _fields_ = [("bmiHeader", _BITMAPINFOHEADER)]

    _user32 = ctypes.windll.user32
    _gdi32 = ctypes.windll.gdi32

    _user32.GetParent.restype = wt.HWND
    _user32.UpdateLayeredWindow.restype = wt.BOOL

# Fonts
MONO_FONT = "JetBrains Mono"
MONO_FALLBACK = "Consolas" if IS_WIN else "Menlo"

# --- Floating Stone palette ---
GREEN = "#42FC93"
GREEN_BRIGHT = "#7AFDB5"
GREEN_DIM = "#1a6b3d"
BLACK = "#000000"
RED = "#FF3333"
AMBER = "#FFD700"

# Surface colors (R, G, B) -- alpha applied separately
SURFACE_DARK = (26, 28, 30)         # #1A1C1E charcoal
SURFACE_DARK_REC = (30, 36, 32)     # #1E2420 warm shift during recording
SURFACE_LIGHT = (245, 245, 243)     # #F5F5F3 warm off-white
SURFACE_LIGHT_REC = (238, 245, 240) # slight green tint during recording

PILL_ALPHA = 235  # 92% opacity

# Recording inner border (RGBA)
REC_BORDER_DARK = (66, 252, 147, 38)
REC_BORDER_LIGHT = (20, 80, 40, 38)


def _composite_at(base, overlay, x, y):
    """Alpha-composite a small overlay onto base at position (x, y)."""
    ox1 = max(0, -x)
    oy1 = max(0, -y)
    ox2 = min(overlay.width, base.width - x)
    oy2 = min(overlay.height, base.height - y)
    if ox2 <= ox1 or oy2 <= oy1:
        return
    crop = overlay.crop((ox1, oy1, ox2, oy2))
    region = base.crop((x + ox1, y + oy1, x + ox2, y + oy2))
    composited = Image.alpha_composite(region, crop)
    base.paste(composited, (x + ox1, y + oy1))


def _lerp_rgb(c1, c2, t):
    """Lerp between two (R,G,B) tuples."""
    t = max(0.0, min(1.0, t))
    return (
        round(c1[0] + (c2[0] - c1[0]) * t),
        round(c1[1] + (c2[1] - c1[1]) * t),
        round(c1[2] + (c2[2] - c1[2]) * t),
    )


# --- DPI scaling ---
def _get_dpi_scale():
    if IS_WIN:
        try:
            hdc = ctypes.windll.user32.GetDC(0)
            dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)
            ctypes.windll.user32.ReleaseDC(0, hdc)
            return dpi / 96.0
        except Exception:
            pass
    return 1.0

_S = _get_dpi_scale()

def _s(val):
    return round(val * _S)

# Pill geometry
PILL_W = _s(120)
PILL_H = _s(48)
PILL_R = PILL_H // 2
SHADOW_PAD = _s(22)

WIN_W = PILL_W + SHADOW_PAD * 2
WIN_H = PILL_H + SHADOW_PAD * 2

PX = SHADOW_PAD
PY = SHADOW_PAD

DOT_CX = PX + PILL_R
DOT_CY = PY + PILL_R
DOT_R = _s(6)

# EQ bars
NUM_BARS = 5
BAR_W = _s(4)
BAR_GAP = _s(5)
BAR_MAX_H = _s(18)
BAR_MIN_H = _s(2)
BAR_WEIGHTS = [0.6, 0.85, 1.0, 0.85, 0.6]

_BARS_TOTAL_W = NUM_BARS * BAR_W + (NUM_BARS - 1) * BAR_GAP
_BARS_AREA_X0 = PX + PILL_H + _s(6)
_BARS_AREA_X1 = PX + PILL_W - _s(10)
_BARS_AREA_W = _BARS_AREA_X1 - _BARS_AREA_X0
BARS_X0 = _BARS_AREA_X0 + (_BARS_AREA_W - _BARS_TOTAL_W) // 2
BARS_CY = PY + PILL_H // 2

RENDER_SCALE = 2

# Shadow
SHADOW_BLUR = _s(12)
SHADOW_Y = _s(4)
SHADOW_ALPHA = 102  # 40%

_dir = os.path.dirname(os.path.abspath(__file__))
ICON_PATH = os.path.join(_dir, "icon.ico")

# --- Precompute drop shadow ---
_SHADOW = Image.new("RGBA", (WIN_W, WIN_H), (0, 0, 0, 0))
_sh = ImageDraw.Draw(_SHADOW)
_sh.rounded_rectangle(
    (PX, PY + SHADOW_Y, PX + PILL_W, PY + PILL_H + SHADOW_Y),
    radius=PILL_R, fill=(0, 0, 0, 255),
)
del _sh
_SHADOW = _SHADOW.filter(ImageFilter.GaussianBlur(radius=SHADOW_BLUR))
_sha = _SHADOW.split()[3].point(lambda p: p * SHADOW_ALPHA // 255)

# Clip mask: zero out alpha near rectangular image edges
_CLIP = Image.new("L", (WIN_W, WIN_H), 0)
_cl = ImageDraw.Draw(_CLIP)
_cl.rounded_rectangle((3, 3, WIN_W - 3, WIN_H - 3), radius=(WIN_H - 6) // 2, fill=255)
_CLIP = _CLIP.filter(ImageFilter.GaussianBlur(radius=4))
del _cl
_sha = ImageChops.multiply(_sha, _CLIP)

_SHADOW.putalpha(_sha)
del _sha


class Overlay:
    def __init__(self, on_quit=None):
        self._on_quit = on_quit

        # -- Window setup --
        if IS_WIN:
            self._root = tk.Tk()
            self._root.title("Bark")
            if os.path.exists(ICON_PATH):
                self._root.iconbitmap(ICON_PATH)
            self._root.protocol("WM_DELETE_WINDOW", self.quit)
            self._root.geometry("1x1+-10000+-10000")
            self._root.attributes("-alpha", 0)
            self._root.resizable(False, False)

            self.root = tk.Toplevel(self._root)
            self.root.title("Bark")
            self.root.overrideredirect(True)
            self.root.attributes("-topmost", True)
            self.root.configure(bg=BLACK)
            if os.path.exists(ICON_PATH):
                self.root.iconbitmap(ICON_PATH)

            self._hwnd = None
            self._hdc_mem = None
            self._hbmp = None
            self._bits = None
        else:
            self._root = tk.Tk()
            self.root = self._root
            self.root.title("Bark")
            self.root.protocol("WM_DELETE_WINDOW", self.quit)
            self.root.withdraw()
            self.root.overrideredirect(True)
            self.root.attributes("-topmost", True)
            try:
                self.root.attributes("-alpha", 0.92)
            except tk.TclError:
                pass
            self.root.configure(bg=BLACK)

        # Font
        self._font = MONO_FONT
        try:
            import tkinter.font as tkfont
            available = tkfont.families(self._root if IS_MAC else None)
            if MONO_FONT not in available:
                self._font = MONO_FALLBACK
        except Exception:
            self._font = MONO_FALLBACK

        # Position
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        if cfg["overlay_x"] is not None and cfg["overlay_y"] is not None:
            x, y = cfg["overlay_x"], cfg["overlay_y"]
        else:
            x = (sw - WIN_W) // 2
            y = sh - WIN_H - 60
        self.root.geometry(f"{WIN_W}x{WIN_H}+{x}+{y}")

        if IS_WIN:
            self.root.withdraw()
        else:
            self.root.deiconify()
        self.root.update_idletasks()

        # Focus steal prevention (Windows)
        self._refocus_enabled = False
        if IS_WIN:
            self.root.bind("<FocusIn>", lambda e: self.root.after(1, self._refocus))
            self._root.after(2000, self._enable_refocus)

        if IS_MAC:
            self._keep_on_top()

        # Drag
        self._drag_x = self._drag_y = 0
        self._save_pos_job = None
        self.root.bind("<Button-1>", self._drag_start)
        self.root.bind("<B1-Motion>", self._drag_move)

        # Right-click
        self.root.bind("<Button-3>", self._show_menu)

        # Visibility / idle
        self._visible = True
        self._idle_job = None

        # Theme
        self._dark = cfg["dark_mode"]
        self._apply_theme_colors()

        # Canvas -- Mac only (Windows uses UpdateLayeredWindow)
        if not IS_WIN:
            self.canvas = tk.Canvas(
                self.root, width=WIN_W, height=WIN_H,
                bg=BLACK, highlightthickness=0, bd=0,
            )
            self.canvas.pack()
            self._canvas_img = self.canvas.create_image(0, 0, anchor="nw")

        # State
        self._state = "idle"
        self._recorder_ref = None
        self._frame = 0
        self._phase = 0.0
        self._anim_job = None
        self._tooltip = None

        # Smooth transition state
        self._bar_vis = 0.0    # 0=hidden, 1=visible (smooth fade)
        self._rec_t = 0.0      # 0=idle surface, 1=recording surface
        self._bar_heights = [0.0] * NUM_BARS

        # Opacity fade for auto-hide
        self._opacity = 1.0
        self._opacity_target = 1.0

        # PIL rendering
        self._photo = None

        # Start
        if IS_WIN:
            self.root.after(50, self._setup_layered)
        else:
            self._animate()

        # Onboarding
        if cfg["first_run"]:
            self._root.after(2000, self._show_onboarding)

    # ============================================================ Win32 layered window

    def _setup_layered(self):
        try:
            self._hwnd = _user32.GetParent(self.root.winfo_id())

            style = _user32.GetWindowLongW(self._hwnd, _GWL_EXSTYLE)
            _user32.SetWindowLongW(self._hwnd, _GWL_EXSTYLE, style | _WS_EX_LAYERED)

            hdc_screen = _user32.GetDC(0)
            self._hdc_mem = _gdi32.CreateCompatibleDC(hdc_screen)
            _user32.ReleaseDC(0, hdc_screen)

            bmi = _BITMAPINFO()
            bmi.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
            bmi.bmiHeader.biWidth = WIN_W
            bmi.bmiHeader.biHeight = -WIN_H
            bmi.bmiHeader.biPlanes = 1
            bmi.bmiHeader.biBitCount = 32

            self._bits = ctypes.c_void_p()
            self._hbmp = _gdi32.CreateDIBSection(
                self._hdc_mem, ctypes.byref(bmi), 0,
                ctypes.byref(self._bits), None, 0,
            )
            _gdi32.SelectObject(self._hdc_mem, self._hbmp)

            log.info(f"Layered window ready (HWND={self._hwnd:#x}, {WIN_W}x{WIN_H})")
        except Exception as e:
            log.error(f"Failed to set up layered window: {e}")
            self._hwnd = None

        self._animate()

        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)

    def _update_layered(self, img):
        if not self._hwnd or not self._bits:
            return

        r, g, b, a = img.split()
        r = ImageChops.multiply(r, a)
        g = ImageChops.multiply(g, a)
        b = ImageChops.multiply(b, a)
        pm = Image.merge("RGBA", (b, g, r, a))

        raw = pm.tobytes("raw", "RGBA")
        ctypes.memmove(self._bits, raw, len(raw))

        pt_src = _POINT(0, 0)
        sz = _SIZE(WIN_W, WIN_H)
        blend = _BLENDFUNCTION(_AC_SRC_OVER, 0, 255, _AC_SRC_ALPHA)

        ok = _user32.UpdateLayeredWindow(
            self._hwnd, None, None, ctypes.byref(sz),
            self._hdc_mem, ctypes.byref(pt_src), 0,
            ctypes.byref(blend), _ULW_ALPHA,
        )
        if not ok and self._frame <= 2:
            log.error(f"UpdateLayeredWindow failed (frame {self._frame})")

    # ============================================================ animation

    def _animate(self):
        # Opacity fade
        self._opacity += (self._opacity_target - self._opacity) * 0.12
        if self._opacity < 0.01 and self._opacity_target == 0.0:
            self._opacity = 0.0
            self._visible = False
            self.root.withdraw()
            if self._anim_job:
                self._root.after_cancel(self._anim_job)
                self._anim_job = None
            return

        # Mac: animate window-level alpha (no per-pixel alpha support)
        if IS_MAC:
            try:
                self.root.attributes("-alpha", max(0.05, self._opacity * 0.92))
            except tk.TclError:
                pass

        self._frame += 1
        self._phase += 0.08

        # Smooth transitions
        bar_target = 1.0 if self._state in ("recording", "transcribing", "done") else 0.0
        self._bar_vis += (bar_target - self._bar_vis) * 0.15

        rec_target = 1.0 if self._state == "recording" else 0.0
        self._rec_t += (rec_target - self._rec_t) * 0.12

        # EQ bar heights
        level = self._get_level()
        for i in range(NUM_BARS):
            if self._state == "recording":
                osc = 0.3 * math.sin(self._phase * (1.2 + i * 0.4) + i * 1.1)
                target = max(0.0, min(1.0, (level + osc) * BAR_WEIGHTS[i]))
            elif self._state == "transcribing":
                target = 0.3 + 0.2 * math.sin(self._phase * 2.0 + i * 0.5)
            elif self._state == "done":
                target = 0.5 + 0.3 * math.sin(self._phase * 1.5 + i * 0.7)
            else:
                target = 0.0
            self._bar_heights[i] += (target - self._bar_heights[i]) * 0.25

        self._render_frame()
        self._anim_job = self._root.after(33, self._animate)

    def _get_level(self):
        if self._recorder_ref and self._state == "recording":
            try:
                return self._recorder_ref.get_level()
            except Exception:
                pass
        return 0.0

    def _render_frame(self):
        rs = RENDER_SCALE

        # 1. Shadow base
        frame = _SHADOW.copy()

        # 2. Dynamic layer at 2x for anti-aliasing
        dyn = Image.new("RGBA", (WIN_W * rs, WIN_H * rs), (0, 0, 0, 0))
        draw = ImageDraw.Draw(dyn)

        # Pill surface (lerps toward recording color when active)
        surf = _lerp_rgb(self._surface, self._surface_rec, self._rec_t)
        pill_fill = (*surf, PILL_ALPHA)

        pill_box = (PX * rs, PY * rs, (PX + PILL_W) * rs, (PY + PILL_H) * rs)
        draw.rounded_rectangle(pill_box, radius=PILL_R * rs, fill=pill_fill)

        # Recording inner border (fades in)
        if self._rec_t > 0.01:
            br, bg_, bb, ba = self._rec_border
            border_color = (br, bg_, bb, round(ba * self._rec_t))
            draw.rounded_rectangle(
                pill_box, radius=PILL_R * rs,
                outline=border_color, width=max(2, _s(2) * rs),
            )

        # EQ bars
        if self._bar_vis > 0.01:
            self._draw_bars(draw, rs)

        # Dot (draws glow + core onto dyn directly)
        self._draw_dot(dyn, rs)

        # 3. Downscale
        dyn = dyn.resize((WIN_W, WIN_H), Image.LANCZOS)

        # 4. Composite
        frame = Image.alpha_composite(frame, dyn)

        # 5. Opacity fade (Windows only - Mac uses window-level alpha)
        if IS_WIN and self._opacity < 0.99:
            a = frame.split()[3]
            a = a.point(lambda p: round(p * self._opacity))
            frame.putalpha(a)

        # 6. Display
        if IS_WIN:
            self._update_layered(frame)
        else:
            bg = Image.new("RGB", (WIN_W, WIN_H), (0, 0, 0))
            bg.paste(frame, (0, 0), frame)
            self._photo = ImageTk.PhotoImage(bg)
            self.canvas.itemconfig(self._canvas_img, image=self._photo)

    def _draw_bars(self, draw, rs):
        if self._bar_vis < 0.01:
            return
        br, bg_, bb = self._bar_color
        alpha = round(255 * self._bar_vis)
        color = (br, bg_, bb, alpha)
        bar_r = BAR_W * rs // 2

        for i in range(NUM_BARS):
            h = BAR_MIN_H + self._bar_heights[i] * (BAR_MAX_H - BAR_MIN_H)
            h = max(BAR_MIN_H, h)
            x = (BARS_X0 + i * (BAR_W + BAR_GAP)) * rs
            cy = BARS_CY * rs
            top = cy - round(h * rs / 2)
            bot = cy + round(h * rs / 2)
            draw.rounded_rectangle(
                (x, top, x + BAR_W * rs, bot),
                radius=bar_r, fill=color,
            )

    def _draw_dot(self, dyn, rs):
        f = self._frame
        st = self._state

        if st == "recording":
            t = (math.sin(f * 0.06) + 1) / 2
            r = DOT_R * (0.85 + 0.3 * t) * rs
            dot_rgb = (255, 51, 51)
            glow_alpha = round(80 + 50 * t)
        elif st == "transcribing":
            r = DOT_R * rs
            dot_rgb = (255, 215, 0)
            glow_alpha = 60
        elif st == "error":
            r = DOT_R * rs
            dot_rgb = (255, 51, 51)
            glow_alpha = 50
        elif st == "done":
            r = DOT_R * rs
            dot_rgb = (122, 253, 181)
            glow_alpha = 90
        else:
            t = (math.sin(f * 0.03) + 1) / 2
            r = DOT_R * rs
            dot_rgb = (66, 252, 147)
            glow_alpha = round(30 + 20 * t)

        cx, cy = DOT_CX * rs, DOT_CY * rs

        # Glow: draw dot on small image, Gaussian blur, composite
        glow_pad = round(DOT_R * 3.5 * rs)
        gw = glow_pad * 2
        glow = Image.new("RGBA", (gw, gw), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        gc = glow_pad
        gd.ellipse(
            (gc - r, gc - r, gc + r, gc + r),
            fill=(*dot_rgb, glow_alpha),
        )
        glow = glow.filter(ImageFilter.GaussianBlur(radius=round(DOT_R * 1.3 * rs)))
        _composite_at(dyn, glow, round(cx - glow_pad), round(cy - glow_pad))

        # Core LED on top
        draw = ImageDraw.Draw(dyn)
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(*dot_rgb, 255))

    # ============================================================ public API

    def set_state(self, state: str):
        try:
            self._root.after(0, self._update_state, state)
        except Exception:
            pass

    def _update_state(self, state: str):
        self._state = state
        if state == "recording":
            self.show_overlay()
        if state in ("idle", "done"):
            self._reset_idle_timer()
        if state == "done":
            self._root.after(1500, self._update_state, "idle")

    def set_sublabel(self, text: str):
        try:
            self._root.after(0, lambda: self._show_tooltip(text))
        except Exception:
            pass

    def flash_transcript(self, text: str):
        snippet = text[:40] + "..." if len(text) > 40 else text
        try:
            self._root.after(0, lambda: self._show_tooltip(snippet, 2500))
        except Exception:
            pass

    def set_recorder(self, recorder):
        self._recorder_ref = recorder

    def run(self):
        self._root.mainloop()

    def quit(self):
        if self._anim_job:
            self._root.after_cancel(self._anim_job)
            self._anim_job = None
        if IS_WIN:
            if self._hbmp:
                _gdi32.DeleteObject(self._hbmp)
            if self._hdc_mem:
                _gdi32.DeleteDC(self._hdc_mem)
        if self._on_quit:
            try:
                self._on_quit()
            except Exception:
                pass
        self._root.quit()

    # ============================================================ tooltip

    def _show_tooltip(self, text, duration_ms=3000):
        if self._tooltip:
            try:
                self._tooltip.destroy()
            except Exception:
                pass
            self._tooltip = None

        tip_bg = "#1A1C1E" if self._dark else "#F5F5F3"
        tip_fg = GREEN if self._dark else "#1A1C1E"

        tip = tk.Toplevel(self._root)
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)
        tip.configure(bg=tip_bg)

        lbl = tk.Label(
            tip, text=text, font=(self._font, 8), fg=tip_fg, bg=tip_bg,
        )
        lbl.pack(padx=8, pady=4)
        tip.update_idletasks()

        tw = tip.winfo_reqwidth()
        ox = self.root.winfo_x() + (WIN_W - tw) // 2
        oy = self.root.winfo_y() - _s(30)
        tip.geometry(f"+{ox}+{oy}")

        self._tooltip = tip
        self._root.after(duration_ms, lambda: self._dismiss_tooltip(tip))

    def _dismiss_tooltip(self, tip):
        if self._tooltip is tip:
            self._tooltip = None
        try:
            tip.destroy()
        except Exception:
            pass

    # ============================================================ window mechanics

    def _keep_on_top(self):
        try:
            self.root.lift()
            self.root.attributes("-topmost", True)
        except Exception:
            pass
        self._root.after(3000, self._keep_on_top)

    def _enable_refocus(self):
        self._refocus_enabled = True

    def _refocus(self):
        if not self._refocus_enabled:
            return
        try:
            self.root.lower()
            self.root.attributes("-topmost", True)
        except Exception:
            pass

    def _drag_start(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _drag_move(self, event):
        x = self.root.winfo_x() + (event.x - self._drag_x)
        y = self.root.winfo_y() + (event.y - self._drag_y)
        self.root.geometry(f"+{x}+{y}")
        if self._save_pos_job:
            self._root.after_cancel(self._save_pos_job)
        self._save_pos_job = self._root.after(500, self._save_position)

    def _save_position(self):
        cfg["overlay_x"] = self.root.winfo_x()
        cfg["overlay_y"] = self.root.winfo_y()
        save_config()

    # ============================================================ right-click menu

    def _show_menu(self, event):
        if self._dark:
            mbg, mfg = "#1A1C1E", GREEN
            mabg, mafg = GREEN, "#1A1C1E"
        else:
            mbg, mfg = "#F5F5F3", "#1A1C1E"
            mabg, mafg = GREEN, "#1A1C1E"

        menu = tk.Menu(
            self.root, tearoff=0,
            bg=mbg, fg=mfg,
            activebackground=mabg, activeforeground=mafg,
            font=(self._font, 9), borderwidth=1, relief="solid",
        )
        sound_label = "Sound: ON" if cfg["sound_enabled"] else "Sound: OFF"
        menu.add_command(label=sound_label, command=self._toggle_sound)
        dark_label = "Dark Mode: ON" if self._dark else "Dark Mode: OFF"
        menu.add_command(label=dark_label, command=self._toggle_dark_mode)
        clip_label = "Mode: Clipboard" if cfg["clipboard_mode"] else "Mode: Type"
        menu.add_command(label=clip_label, command=self._toggle_clipboard_mode)
        menu.add_separator()
        menu.add_command(label="Quit", command=self.quit)
        menu.tk_popup(event.x_root, event.y_root)

    def _toggle_sound(self):
        cfg["sound_enabled"] = not cfg["sound_enabled"]
        save_config()

    def _toggle_clipboard_mode(self):
        cfg["clipboard_mode"] = not cfg["clipboard_mode"]
        save_config()
        mode = "CLIPBOARD" if cfg["clipboard_mode"] else "TYPE"
        self._show_tooltip(mode, 1500)

    def _toggle_dark_mode(self):
        self._dark = not self._dark
        cfg["dark_mode"] = self._dark
        save_config()
        self._apply_theme_colors()

    def _apply_theme_colors(self):
        if self._dark:
            self._surface = SURFACE_DARK
            self._surface_rec = SURFACE_DARK_REC
            self._rec_border = REC_BORDER_DARK
            self._bar_color = (66, 252, 147)    # bright green
        else:
            self._surface = SURFACE_LIGHT
            self._surface_rec = SURFACE_LIGHT_REC
            self._rec_border = REC_BORDER_LIGHT
            self._bar_color = (10, 138, 66)     # deep green #0A8A42

    # ============================================================ idle auto-hide

    def _reset_idle_timer(self):
        if self._idle_job:
            self._root.after_cancel(self._idle_job)
            self._idle_job = None
        timeout = cfg["idle_timeout"]
        if timeout > 0:
            self._idle_job = self._root.after(
                int(timeout * 1000), self._hide_overlay
            )

    def _hide_overlay(self):
        self._opacity_target = 0.0
        # Animation loop handles the fade + withdraw when opacity reaches 0

    def show_overlay(self):
        if not self._visible:
            self._visible = True
            self._opacity = max(self._opacity, 0.01)
            self.root.deiconify()
            self.root.lift()
            if IS_WIN:
                self.root.attributes("-topmost", True)
            if not self._anim_job:
                self._animate()
        self._opacity_target = 1.0
        self._reset_idle_timer()

    # ============================================================ first-run tooltip

    def _show_onboarding(self):
        tip_bg = "#1A1C1E" if self._dark else "#F5F5F3"
        tip_fg = GREEN if self._dark else "#1A1C1E"

        tip = tk.Toplevel(self._root)
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)
        tip.configure(bg=tip_bg)
        ox = self.root.winfo_x()
        oy = self.root.winfo_y() - _s(55)
        tip.geometry(f"{_s(260)}x{_s(40)}+{ox}+{oy}")
        tk.Label(
            tip,
            text=f"Hold {TRIGGER_KEY_NAME} to talk\nRight-click for options",
            font=(self._font, 8), fg=tip_fg, bg=tip_bg, justify="left",
        ).pack(padx=10, pady=6)
        self._root.after(6000, lambda: self._dismiss_onboarding(tip))

    def _dismiss_onboarding(self, tip):
        try:
            tip.destroy()
        except Exception:
            pass
        cfg["first_run"] = False
        save_config()
