import logging
import queue
import threading
import time
from pynput import keyboard
import pyperclip
from config import cfg, IS_WIN, IS_MAC

if IS_WIN:
    import ctypes
    from config import VK_CAPITAL

if IS_MAC:
    from Quartz import (
        CGEventTapCreate,
        CGEventTapEnable,
        CGEventGetIntegerValueField,
        CGEventGetFlags,
        CFMachPortCreateRunLoopSource,
        CFRunLoopGetCurrent,
        CFRunLoopAddSource,
        CFRunLoopRemoveSource,
        CFRunLoopRun,
        CFRunLoopStop,
        kCGSessionEventTap,
        kCGHeadInsertEventTap,
        kCGEventFlagsChanged,
        kCGKeyboardEventKeycode,
        kCGEventFlagMaskAlternate,
        kCGEventFlagMaskCommand,
        kCFRunLoopCommonModes,
    )

log = logging.getLogger(__name__)

# Windows constants
WM_KEYDOWN = 256
WM_KEYUP = 257
KEYEVENTF_KEYUP = 0x2

# Mac trigger key mappings: keycode + flag mask
_MAC_TRIGGER_KEYS = {
    "right_option":  (0x3D, kCGEventFlagMaskAlternate if IS_MAC else 0),
    "right_command": (0x36, kCGEventFlagMaskCommand if IS_MAC else 0),
}

# Quartz event tap special types (not always exported by PyObjC)
_TAP_DISABLED_BY_TIMEOUT = 0xFFFFFFFE


class KeyboardHook:
    def __init__(self, on_record_start, on_record_stop):
        self._on_record_start = on_record_start
        self._on_record_stop = on_record_stop
        self._pressed = False
        self._listener = None  # pynput Listener (Windows only)
        self._controller = keyboard.Controller()
        self._tap = None  # Quartz event tap (Mac only)
        self._tap_source = None  # CFRunLoopSource (Mac only)
        self._tap_loop = None  # CFRunLoop for tap thread (Mac only)
        self._tap_ready = threading.Event()
        self._tap_failed = False
        self._events = queue.Queue()  # Mac: decouple Quartz callback from Python work
        if IS_MAC:
            trigger = cfg["trigger_key_mac"]
            self._mac_keycode, self._mac_flag_mask = _MAC_TRIGGER_KEYS.get(
                trigger, _MAC_TRIGGER_KEYS["right_option"]
            )
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

    # --- Mac-specific (Quartz CGEventTap on dedicated thread) ---

    def _mac_event_callback(self, proxy, event_type, event, refcon):
        """Quartz event tap callback. Runs on the tap thread's CFRunLoop.

        IMPORTANT: Do minimal Python work here to avoid GIL conflicts with
        sounddevice's PortAudio thread. Just queue events for the main thread.
        """
        # Re-enable if macOS disabled the tap due to slow callback
        if event_type == _TAP_DISABLED_BY_TIMEOUT:
            CGEventTapEnable(self._tap, True)
            return event

        if event_type != kCGEventFlagsChanged:
            return event

        keycode = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)
        if keycode != self._mac_keycode:
            return event

        flags = CGEventGetFlags(event)
        key_down = bool(flags & self._mac_flag_mask)

        if key_down and not self._pressed:
            self._pressed = True
            self._events.put("start")
        elif not key_down and self._pressed:
            self._pressed = False
            self._events.put("stop")

        return event

    def _run_tap(self):
        """Run Quartz event tap on a dedicated thread with its own CFRunLoop.

        This avoids GIL reentrancy: tkinter's mainloop releases the GIL into
        Tcl/Tk, which drives the CFRunLoop. If the Quartz callback fires inside
        that CFRunLoop, it re-enters Python with corrupted thread state, crashing
        sounddevice's PortAudio callback thread. A separate CFRunLoop avoids this.
        """
        mask = 1 << kCGEventFlagsChanged
        self._tap = CGEventTapCreate(
            kCGSessionEventTap,
            kCGHeadInsertEventTap,
            0,  # active tap
            mask,
            self._mac_event_callback,
            None,
        )

        if self._tap is None:
            log.error(
                "Failed to create event tap - Accessibility permission not granted. "
                "Open System Settings > Privacy & Security > Accessibility and add Bark."
            )
            self._tap_failed = True
            self._tap_ready.set()
            return

        self._tap_source = CFMachPortCreateRunLoopSource(None, self._tap, 0)
        self._tap_loop = CFRunLoopGetCurrent()
        CFRunLoopAddSource(self._tap_loop, self._tap_source, kCFRunLoopCommonModes)
        CGEventTapEnable(self._tap, True)

        key_name = cfg["trigger_key_mac"].replace("_", " ").title()
        log.info(f"Quartz event tap active ({key_name} key).")
        self._tap_ready.set()
        CFRunLoopRun()  # Block on this thread's run loop

    def poll_events(self):
        """Process queued keyboard events. Call from tkinter after() loop."""
        try:
            while True:
                event = self._events.get_nowait()
                if event == "start":
                    try:
                        self._on_record_start()
                    except Exception as e:
                        log.error(f"Record start failed: {e}")
                elif event == "stop":
                    threading.Thread(
                        target=self._safe_record_stop, daemon=True
                    ).start()
        except queue.Empty:
            pass

    # --- Shared ---

    def _safe_record_stop(self):
        try:
            self._on_record_stop()
        except Exception as e:
            log.error(f"Record stop failed: {e}")

    def type_text(self, text: str):
        # Clipboard mode: just copy, don't paste
        if cfg["clipboard_mode"]:
            pyperclip.copy(text)
            return

        try:
            old_clipboard = pyperclip.paste()
        except Exception:
            old_clipboard = ""

        # Cmd+V on Mac, Ctrl+V on Windows
        paste_modifier = keyboard.Key.cmd if IS_MAC else keyboard.Key.ctrl

        try:
            pyperclip.copy(text)
            time.sleep(cfg["paste_delay"])
            self._controller.press(paste_modifier)
            self._controller.press("v")
            self._controller.release("v")
            self._controller.release(paste_modifier)
            time.sleep(cfg["paste_delay"])
        except Exception as e:
            log.error(f"Paste failed: {e}")
        finally:
            try:
                pyperclip.copy(old_clipboard)
            except Exception:
                pass

    def start(self) -> bool:
        """Start keyboard monitoring. Returns True on success, False on failure."""
        if IS_WIN:
            self._listener = keyboard.Listener(
                on_press=lambda key: None,
                on_release=lambda key: None,
                win32_event_filter=self._win32_event_filter,
            )
            self._listener.start()
        else:
            # Run Quartz CGEventTap on a dedicated thread to avoid GIL
            # reentrancy with tkinter's mainloop + sounddevice's PortAudio.
            log.info("macOS: Keyboard monitoring requires Accessibility permission.")
            log.info("macOS: Grant in System Settings > Privacy & Security > Accessibility.")

            self._tap_ready = threading.Event()
            self._tap_failed = False
            threading.Thread(target=self._run_tap, daemon=True).start()

            self._tap_ready.wait(timeout=5.0)
            if self._tap_failed:
                return False

        log.info("Keyboard listener started.")
        return True

    def stop(self):
        if self._listener:
            self._listener.stop()
            if IS_WIN:
                self._restore_caps_state()
        if IS_MAC:
            if self._tap_source and self._tap_loop:
                try:
                    CFRunLoopRemoveSource(
                        self._tap_loop, self._tap_source, kCFRunLoopCommonModes
                    )
                except Exception:
                    pass
            if self._tap:
                try:
                    CGEventTapEnable(self._tap, False)
                except Exception:
                    pass
            if self._tap_loop:
                try:
                    CFRunLoopStop(self._tap_loop)
                except Exception:
                    pass
