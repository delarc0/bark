import logging
import os
import random
import tkinter as tk

log = logging.getLogger(__name__)

# LAB37 design system
GREEN = "#42FC93"
GREEN_DIM = "#1a6b3d"
GREEN_GLOW = "#2aad62"
BLACK = "#000000"
SURFACE = "#111113"
BORDER = "#27272A"
TEXT_DIM = "#52525B"
TEXT_MED = "#A1A1AA"
RED = "#FF3333"
RED_DIM = "#661111"
AMBER = "#FFD700"
AMBER_DIM = "#665800"

STATE_COLORS = {
    "idle": TEXT_DIM,
    "recording": RED,
    "transcribing": AMBER,
    "done": GREEN,
}

STATE_BORDERS = {
    "idle": BORDER,
    "recording": RED,
    "transcribing": AMBER,
    "done": GREEN,
}

LABELS = {
    "idle": "STANDBY",
    "recording": "REC",
    "transcribing": "PROCESSING",
    "done": "TRANSMITTED",
}

WIDTH = 280
HEIGHT = 52

# Waveform config
NUM_BARS = 20
BAR_WIDTH = 3
BAR_GAP = 3
BAR_START_X = 152
BAR_Y_CENTER = 24
BAR_MAX_H = 14

_dir = os.path.dirname(os.path.abspath(__file__))
ICON_PATH = os.path.join(_dir, "icon.ico")


class Overlay:
    def __init__(self, on_quit=None):
        self._on_quit = on_quit

        # Hidden root window provides the taskbar icon
        self._root = tk.Tk()
        self._root.withdraw()
        self._root.title("LAB37 Dictation")
        if os.path.exists(ICON_PATH):
            self._root.iconbitmap(ICON_PATH)

        # Visible overlay is a Toplevel child
        self.root = tk.Toplevel(self._root)
        self.root.title("LAB37 Dictation")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.92)
        self.root.configure(bg=BLACK)
        if os.path.exists(ICON_PATH):
            self.root.iconbitmap(ICON_PATH)

        # Center at bottom of screen
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = (screen_w - WIDTH) // 2
        y = screen_h - HEIGHT - 60
        self.root.geometry(f"{WIDTH}x{HEIGHT}+{x}+{y}")

        # Prevent stealing focus
        self.root.bind("<FocusIn>", lambda e: self.root.after(1, self._refocus))

        # Right-click to quit
        self.root.bind("<Button-3>", self._show_menu)

        # Outer glow frame (border changes color with state)
        self._glow_frame = tk.Frame(self.root, bg=BORDER)
        self._glow_frame.pack(fill="both", expand=True, padx=0, pady=0)

        # Inner black surface
        inner = tk.Frame(self._glow_frame, bg=BLACK)
        inner.pack(fill="both", expand=True, padx=1, pady=1)

        # Main canvas for custom rendering
        self.canvas = tk.Canvas(
            inner, bg=BLACK, highlightthickness=0,
            width=WIDTH - 2, height=HEIGHT - 2,
        )
        self.canvas.pack(fill="both", expand=True)

        # Scanlines (subtle CRT effect)
        for y_line in range(0, HEIGHT, 4):
            self.canvas.create_line(
                0, y_line, WIDTH, y_line,
                fill="#ffffff", stipple="gray12",
            )

        # Status indicator (square, not circle - LAB37 has no rounded corners)
        self._indicator = self.canvas.create_rectangle(
            14, 16, 26, 28,
            fill=TEXT_DIM, outline="",
        )

        # Status text
        self._status_text = self.canvas.create_text(
            40, 15,
            text="STANDBY",
            font=("Consolas", 13, "bold"),
            fill=TEXT_DIM,
            anchor="nw",
        )

        # Small sublabel
        self._label = self.canvas.create_text(
            40, 35,
            text="DICTATION",
            font=("Consolas", 7),
            fill=TEXT_DIM,
            anchor="nw",
        )

        # Waveform baseline (subtle scope line)
        bar_end_x = BAR_START_X + NUM_BARS * (BAR_WIDTH + BAR_GAP)
        self.canvas.create_line(
            BAR_START_X, BAR_Y_CENTER, bar_end_x, BAR_Y_CENTER,
            fill=GREEN_DIM, dash=(2, 4),
        )

        # Waveform bars
        self._bars = []
        for i in range(NUM_BARS):
            x = BAR_START_X + i * (BAR_WIDTH + BAR_GAP)
            bar = self.canvas.create_rectangle(
                x, BAR_Y_CENTER, x + BAR_WIDTH, BAR_Y_CENTER,
                fill=GREEN, outline="", state="hidden",
            )
            self._bars.append(bar)
        self._bar_heights = [0.0] * NUM_BARS
        self._wave_job = None
        self._recorder_ref = None

        self._state = "idle"
        self._pulse_on = True
        self._pulse_job = None

    def _show_menu(self, event):
        menu = tk.Menu(
            self.root, tearoff=0,
            bg=SURFACE, fg=TEXT_MED,
            activebackground=GREEN_DIM, activeforeground=GREEN,
            font=("Consolas", 9),
            borderwidth=1,
            relief="solid",
        )
        menu.add_command(label="Quit", command=self.quit)
        menu.tk_popup(event.x_root, event.y_root)

    def _refocus(self):
        try:
            self.root.lower()
            self.root.attributes("-topmost", True)
        except Exception:
            pass

    def set_recorder(self, recorder):
        self._recorder_ref = recorder

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
            if h > 0.5:
                self.canvas.itemconfig(bar, fill=GREEN)
            elif h > 0.2:
                self.canvas.itemconfig(bar, fill=GREEN_GLOW)
            else:
                self.canvas.itemconfig(bar, fill=GREEN_DIM)

        self._wave_job = self._root.after(60, self._update_wave)

    def set_state(self, state: str):
        try:
            self._root.after(0, self._update_state, state)
        except Exception:
            pass

    def _update_state(self, state: str):
        self._state = state
        color = STATE_COLORS.get(state, TEXT_DIM)
        border_color = STATE_BORDERS.get(state, BORDER)
        text = LABELS.get(state, "STANDBY")

        if self._pulse_job:
            self._root.after_cancel(self._pulse_job)
            self._pulse_job = None

        # Update border glow
        self._glow_frame.configure(bg=border_color)

        # Update indicator and text
        self.canvas.itemconfig(self._indicator, fill=color)
        self.canvas.itemconfig(self._status_text, text=text, fill=color)

        # Sublabel changes with state
        if state == "idle":
            self.canvas.itemconfig(self._label, text="DICTATION", fill=TEXT_DIM)
        elif state == "recording":
            self.canvas.itemconfig(self._label, text="LISTENING", fill=RED_DIM)
        elif state == "transcribing":
            self.canvas.itemconfig(self._label, text="WHISPER AI", fill=AMBER_DIM)
        elif state == "done":
            self.canvas.itemconfig(self._label, text="COMPLETE", fill=GREEN_DIM)

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
            self.canvas.itemconfig(self._indicator, fill=RED)
            self._glow_frame.configure(bg=RED)
        else:
            self.canvas.itemconfig(self._indicator, fill=RED_DIM)
            self._glow_frame.configure(bg=RED_DIM)
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
