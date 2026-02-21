import logging
import threading
import time
from pynput import keyboard
import pyperclip
from config import PASTE_DELAY, IS_WIN, IS_MAC

if IS_WIN:
    import ctypes
    from config import VK_CAPITAL

log = logging.getLogger(__name__)

# Windows constants
WM_KEYDOWN = 256
WM_KEYUP = 257
KEYEVENTF_KEYUP = 0x2

# Mac trigger key
MAC_TRIGGER = keyboard.Key.alt_r  # Right Option


class KeyboardHook:
    def __init__(self, on_record_start, on_record_stop):
        self._on_record_start = on_record_start
        self._on_record_stop = on_record_stop
        self._pressed = False
        self._listener = None
        self._controller = keyboard.Controller()
        if IS_WIN:
            self._initial_caps_state = self._get_caps_state()

    # --- Windows-specific ---

    def _get_caps_state(self) -> bool:
        return bool(ctypes.windll.user32.GetKeyState(VK_CAPITAL) & 0x0001)

    def _restore_caps_state(self):
        current = self._get_caps_state()
        if current != self._initial_caps_state:
            ctypes.windll.user32.keybd_event(VK_CAPITAL, 0x45, 0, 0)
            ctypes.windll.user32.keybd_event(VK_CAPITAL, 0x45, KEYEVENTF_KEYUP, 0)

    def _win32_event_filter(self, msg, data):
        if data.vkCode == VK_CAPITAL:
            if msg == WM_KEYDOWN and not self._pressed:
                self._pressed = True
                try:
                    self._on_record_start()
                except Exception as e:
                    log.error(f"Record start failed: {e}")
            elif msg == WM_KEYUP and self._pressed:
                self._pressed = False
                threading.Thread(
                    target=self._safe_record_stop, daemon=True
                ).start()
            self._listener.suppress_event()

    # --- Mac-specific ---

    def _on_press_mac(self, key):
        if key == MAC_TRIGGER and not self._pressed:
            self._pressed = True
            try:
                self._on_record_start()
            except Exception as e:
                log.error(f"Record start failed: {e}")

    def _on_release_mac(self, key):
        if key == MAC_TRIGGER and self._pressed:
            self._pressed = False
            threading.Thread(
                target=self._safe_record_stop, daemon=True
            ).start()

    # --- Shared ---

    def _safe_record_stop(self):
        try:
            self._on_record_stop()
        except Exception as e:
            log.error(f"Record stop failed: {e}")

    def type_text(self, text: str):
        try:
            old_clipboard = pyperclip.paste()
        except Exception:
            old_clipboard = ""

        # Cmd+V on Mac, Ctrl+V on Windows
        paste_modifier = keyboard.Key.cmd if IS_MAC else keyboard.Key.ctrl

        try:
            pyperclip.copy(text)
            time.sleep(PASTE_DELAY)
            self._controller.press(paste_modifier)
            self._controller.press("v")
            self._controller.release("v")
            self._controller.release(paste_modifier)
            time.sleep(PASTE_DELAY)
        except Exception as e:
            log.error(f"Paste failed: {e}")
        finally:
            try:
                pyperclip.copy(old_clipboard)
            except Exception:
                pass

    def start(self):
        if IS_WIN:
            self._listener = keyboard.Listener(
                on_press=lambda key: None,
                on_release=lambda key: None,
                win32_event_filter=self._win32_event_filter,
            )
        else:
            self._listener = keyboard.Listener(
                on_press=self._on_press_mac,
                on_release=self._on_release_mac,
            )
        self._listener.start()

    def stop(self):
        if self._listener:
            self._listener.stop()
            if IS_WIN:
                self._restore_caps_state()
