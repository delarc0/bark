import logging
import os
import random
import tkinter as tk

from config import IS_WIN, IS_MAC

log = logging.getLogger(__name__)

# Register as a proper Windows app so the taskbar icon is pinnable
if IS_WIN:
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("lab37.bark")
    except Exception:
        pass

# Font: JetBrains Mono preferred, fallback to platform monospace
MONO_FONT = "JetBrains Mono"
MONO_FALLBACK = "Consolas" if IS_WIN else "Menlo"

# LAB37 design system
GREEN = "#42FC93"
GREEN_BRIGHT = "#7AFDB5"
GREEN_DIM = "#1a6b3d"
GREEN_GLOW = "#2aad62"
GREEN_DARK = "#0d3520"
BLACK = "#000000"
RED = "#FF3333"
RED_DIM = "#661111"
AMBER = "#FFD700"
AMBER_DIM = "#665800"

# Text/indicator color per state
STATE_COLORS = {
    "loading": BLACK,
    "idle": BLACK,
    "recording": BLACK,
    "transcribing": BLACK,
    "done": BLACK,
    "error": BLACK,
}

# Outer diffuse glow layer
STATE_GLOW = {
    "loading": AMBER_DIM,
    "idle": GREEN_DIM,
    "recording": GREEN,
    "transcribing": AMBER_DIM,
    "done": GREEN,
    "error": RED_DIM,
}

# Bright inner edge
STATE_EDGE = {
    "loading": AMBER,
    "idle": GREEN_GLOW,
    "recording": GREEN_BRIGHT,
    "transcribing": AMBER,
    "done": GREEN_BRIGHT,
    "error": RED,
}

# Indicator square color (separate from text)
STATE_INDICATOR = {
    "loading": AMBER,
    "idle": GREEN_DARK,
    "recording": RED,
    "transcribing": AMBER,
    "done": GREEN_DARK,
    "error": RED,
}

LABELS = {
    "loading": "LOADING",
    "idle": "STANDBY",
    "recording": "REC",
    "transcribing": "PROCESSING",
    "done": "TRANSMITTED",
    "error": "ERROR",
}

WIDTH = 260
HEIGHT = 64

# Waveform config
NUM_BARS = 16
BAR_WIDTH = 3
BAR_GAP = 2
BAR_START_X = 140
BAR_Y_CENTER = 25
BAR_MAX_H = 18

_dir = os.path.dirname(os.path.abspath(__file__))
ICON_PATH = os.path.join(_dir, "icon.ico")


class Overlay:
    def __init__(self, on_quit=None):
        self._on_quit = on_quit

        if IS_WIN:
            # Windows: Root window lives in the taskbar (NOT withdrawn - withdraw hides from taskbar)
            self._root = tk.Tk()
            self._root.title("Bark")
            if os.path.exists(ICON_PATH):
                self._root.iconbitmap(ICON_PATH)
            self._root.protocol("WM_DELETE_WINDOW", self.quit)
            # Invisible but present in taskbar: off-screen + fully transparent
            self._root.geometry("1x1+-10000+-10000")
            self._root.attributes("-alpha", 0)
            self._root.resizable(False, False)

            # Visible overlay is a borderless Toplevel child
            self.root = tk.Toplevel(self._root)
            self.root.title("Bark")
            self.root.overrideredirect(True)
            self.root.attributes("-topmost", True)
            self.root.attributes("-alpha", 0.85)
            self.root.configure(bg=BLACK)
            if os.path.exists(ICON_PATH):
                self.root.iconbitmap(ICON_PATH)
        else:
            # Mac: Single root window as overlay (no Toplevel -- avoids Cocoa rendering bugs)
            self._root = tk.Tk()
            self.root = self._root
            self.root.title("Bark")
            self.root.protocol("WM_DELETE_WINDOW", self.quit)
            # Withdraw before configuring to prevent flash of normal window
            self.root.withdraw()
            self.root.overrideredirect(True)
            self.root.attributes("-topmost", True)
            try:
                self.root.attributes("-alpha", 0.85)
            except tk.TclError:
                pass
            self.root.configure(bg=BLACK)

        # Resolve font (check if JetBrains Mono is available)
        self._font = MONO_FONT
        try:
            import tkinter.font as tkfont
            available = tkfont.families(self._root if IS_MAC else None)
            if MONO_FONT not in available:
                self._font = MONO_FALLBACK
        except Exception:
            self._font = MONO_FALLBACK

        # Center at bottom of screen
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = (screen_w - WIDTH) // 2
        y = screen_h - HEIGHT - 60
        self.root.geometry(f"{WIDTH}x{HEIGHT}+{x}+{y}")

        # Show the window now that geometry is set (Mac: was withdrawn during setup)
        if IS_MAC:
            self.root.deiconify()
        self.root.lift()
        self.root.update_idletasks()

        # Prevent stealing focus (Windows only - Mac overlay doesn't need this
        # and the lower/re-topmost cycling causes System Settings to disappear)
        self._refocus_enabled = False
        if IS_WIN:
            self.root.bind("<FocusIn>", lambda e: self.root.after(1, self._refocus))
            self._root.after(2000, self._enable_refocus)

        # Drag to move
        self._drag_x = 0
        self._drag_y = 0
        self.root.bind("<Button-1>", self._drag_start)
        self.root.bind("<B1-Motion>", self._drag_move)

        # Right-click to quit
        self.root.bind("<Button-3>", self._show_menu)

        # Glow halo (outermost, visible during recording)
        self._glow_halo = tk.Frame(self.root, bg=BLACK)
        self._glow_halo.pack(fill="both", expand=True, padx=0, pady=0)

        # Outer glow layer
        self._glow_outer = tk.Frame(self._glow_halo, bg=GREEN_DIM)
        self._glow_outer.pack(fill="both", expand=True, padx=3, pady=3)

        # Bright inner edge
        self._glow_edge = tk.Frame(self._glow_outer, bg=GREEN_GLOW)
        self._glow_edge.pack(fill="both", expand=True, padx=1, pady=1)

        # Green button surface
        inner = tk.Frame(self._glow_edge, bg=GREEN)
        inner.pack(fill="both", expand=True, padx=1, pady=1)

        # Main canvas
        self.canvas = tk.Canvas(
            inner, bg=GREEN, highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True)

        # Scanlines (subtle CRT effect)
        if IS_WIN:
            for y_line in range(0, HEIGHT, 4):
                self.canvas.create_line(
                    0, y_line, WIDTH, y_line,
                    fill=BLACK, stipple="gray12",
                )
        else:
            for y_line in range(0, HEIGHT, 4):
                self.canvas.create_line(
                    0, y_line, WIDTH, y_line,
                    fill=GREEN_GLOW, width=1,
                )

        # Status indicator square (vertically centered)
        sq_size = 10
        sq_x = 10
        sq_y = BAR_Y_CENTER - sq_size // 2
        self._indicator = self.canvas.create_rectangle(
            sq_x, sq_y, sq_x + sq_size, sq_y + sq_size,
            fill=GREEN_DARK, outline="",
        )

        # Status text (vertically centered top half)
        self._status_text = self.canvas.create_text(
            28, 9,
            text="STANDBY",
            font=(self._font, 14, "bold"),
            fill=BLACK,
            anchor="nw",
        )

        # Sublabel (vertically centered bottom half)
        self._label = self.canvas.create_text(
            28, 30,
            text="DICTATION",
            font=(self._font, 8),
            fill=GREEN_DARK,
            anchor="nw",
        )

        # Waveform baseline
        bar_end_x = BAR_START_X + NUM_BARS * (BAR_WIDTH + BAR_GAP)
        self.canvas.create_line(
            BAR_START_X, BAR_Y_CENTER, bar_end_x, BAR_Y_CENTER,
            fill=GREEN_GLOW, dash=(2, 4),
        )

        # Waveform bars
        self._bars = []
        for i in range(NUM_BARS):
            bx = BAR_START_X + i * (BAR_WIDTH + BAR_GAP)
            bar = self.canvas.create_rectangle(
                bx, BAR_Y_CENTER, bx + BAR_WIDTH, BAR_Y_CENTER,
                fill=BLACK, outline="", state="hidden",
            )
            self._bars.append(bar)
        self._bar_heights = [0.0] * NUM_BARS
        self._wave_job = None
        self._recorder_ref = None

        self._state = "idle"
        self._pulse_on = True
        self._pulse_job = None

    def _drag_start(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _drag_move(self, event):
        x = self.root.winfo_x() + (event.x - self._drag_x)
        y = self.root.winfo_y() + (event.y - self._drag_y)
        self.root.geometry(f"+{x}+{y}")

    def _show_menu(self, event):
        menu = tk.Menu(
            self.root, tearoff=0,
            bg=GREEN, fg=BLACK,
            activebackground=GREEN_BRIGHT, activeforeground=BLACK,
            font=(self._font, 9),
            borderwidth=1,
            relief="solid",
        )
        menu.add_command(label="Quit", command=self.quit)
        menu.tk_popup(event.x_root, event.y_root)

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

    def set_recorder(self, recorder):
        self._recorder_ref = recorder

    def set_sublabel(self, text: str):
        """Update sublabel text without changing state (for loading progress)."""
        try:
            self._root.after(0, lambda: self.canvas.itemconfig(self._label, text=text))
        except Exception:
            pass

    def _start_wave(self):
        self._bar_heights = [0.0] * NUM_BARS
        for bar in self._bars:
            self.canvas.itemconfig(bar, state="normal")
        self._update_wave()

    def _stop_wave(self):
        if self._wave_job:
            self._root.after_cancel(self._wave_job)
            self._wave_job = None
        for bar in self._bars:
            self.canvas.itemconfig(bar, state="hidden")
        self._bar_heights = [0.0] * NUM_BARS

    def _update_wave(self):
        if self._state != "recording":
            return

        level = 0.0
        if self._recorder_ref:
            try:
                level = self._recorder_ref.get_level()
            except Exception:
                pass

        # Scroll left, add newest level on right
        self._bar_heights = self._bar_heights[1:] + [level]

        for i, bar in enumerate(self._bars):
            h = self._bar_heights[i]
            h *= (0.85 + random.random() * 0.3)
            pixel_h = max(1, int(h * BAR_MAX_H))
            x = BAR_START_X + i * (BAR_WIDTH + BAR_GAP)
            self.canvas.coords(bar, x, BAR_Y_CENTER - pixel_h,
                               x + BAR_WIDTH, BAR_Y_CENTER + pixel_h)
            # All bars black on green bg
            self.canvas.itemconfig(bar, fill=BLACK)

        self._wave_job = self._root.after(60, self._update_wave)

    def set_state(self, state: str):
        try:
            self._root.after(0, self._update_state, state)
        except Exception:
            pass

    def _update_state(self, state: str):
        self._state = state
        color = STATE_COLORS.get(state, BLACK)
        indicator = STATE_INDICATOR.get(state, GREEN_DARK)
        glow = STATE_GLOW.get(state, GREEN_DIM)
        edge = STATE_EDGE.get(state, GREEN_GLOW)
        text = LABELS.get(state, "STANDBY")

        if self._pulse_job:
            self._root.after_cancel(self._pulse_job)
            self._pulse_job = None

        # Update glow layers (halo is outermost, only visible during recording)
        self._glow_halo.configure(bg=BLACK)
        self._glow_outer.configure(bg=glow)
        self._glow_edge.configure(bg=edge)

        # Update indicator and text
        self.canvas.itemconfig(self._indicator, fill=indicator)
        self.canvas.itemconfig(self._status_text, text=text, fill=color)

        # Sublabel changes with state
        sublabels = {
            "loading": "INITIALIZING",
            "idle": "DICTATION",
            "recording": "LISTENING",
            "transcribing": "WHISPER AI",
            "done": "COMPLETE",
            "error": "CHECK LOG",
        }
        self.canvas.itemconfig(
            self._label, text=sublabels.get(state, ""), fill=GREEN_DARK
        )

        if state == "recording":
            self._pulse_on = True
            self._pulse()
            self._start_wave()
        else:
            self._stop_wave()

        if state == "done":
            self._root.after(1500, self._update_state, "idle")

    def _pulse(self):
        if self._state != "recording":
            return
        self._pulse_on = not self._pulse_on
        if self._pulse_on:
            # Intense glow - emanating halo
            self._glow_halo.configure(bg=GREEN_DARK)
            self._glow_outer.configure(bg=GREEN)
            self._glow_edge.configure(bg=GREEN_BRIGHT)
            self.canvas.itemconfig(self._indicator, fill=RED)
        else:
            # Subtle dip
            self._glow_halo.configure(bg=GREEN_DIM)
            self._glow_outer.configure(bg=GREEN_GLOW)
            self._glow_edge.configure(bg=GREEN)
            self.canvas.itemconfig(self._indicator, fill=RED_DIM)
        self._pulse_job = self._root.after(500, self._pulse)

    def run(self):
        self._root.mainloop()

    def quit(self):
        if self._pulse_job:
            self._root.after_cancel(self._pulse_job)
            self._pulse_job = None
        if self._on_quit:
            try:
                self._on_quit()
            except Exception:
                pass
        self._root.quit()
