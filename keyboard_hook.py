import logging
import threading
import time
from pynput import keyboard
import pyperclip
from config import PASTE_DELAY, IS_WIN, IS_MAC

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
        CFRunLoopGetMain,
        CFRunLoopAddSource,
        CFRunLoopRemoveSource,
        kCGSessionEventTap,
        kCGHeadInsertEventTap,
        kCGEventFlagsChanged,
        kCGKeyboardEventKeycode,
        kCGEventFlagMaskAlternate,
        kCFRunLoopCommonModes,
    )

log = logging.getLogger(__name__)

# Windows constants
WM_KEYDOWN = 256
WM_KEYUP = 257
KEYEVENTF_KEYUP = 0x2

# Mac: Right Option keycode (0x3D = 61)
MAC_RIGHT_OPTION_KEYCODE = 0x3D

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

    # --- Mac-specific (Quartz CGEventTap - runs on main thread) ---

    def _mac_event_callback(self, proxy, event_type, event, refcon):
        """Quartz event tap callback. Runs on the main thread's CFRunLoop."""
        # Re-enable if macOS disabled the tap due to slow callback
        if event_type == _TAP_DISABLED_BY_TIMEOUT:
            log.warning("Event tap timed out, re-enabling...")
            CGEventTapEnable(self._tap, True)
            return event

        if event_type != kCGEventFlagsChanged:
            return event

        keycode = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)
        if keycode != MAC_RIGHT_OPTION_KEYCODE:
            return event

        flags = CGEventGetFlags(event)
        option_down = bool(flags & kCGEventFlagMaskAlternate)

        if option_down and not self._pressed:
            self._pressed = True
            log.debug("Right Option pressed (Quartz)")
            try:
                self._on_record_start()
            except Exception as e:
                log.error(f"Record start failed: {e}")
        elif not option_down and self._pressed:
            self._pressed = False
            log.debug("Right Option released (Quartz)")
            threading.Thread(
                target=self._safe_record_stop, daemon=True
            ).start()

        return event

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
            # Quartz CGEventTap replaces pynput Listener on macOS.
            # pynput's Listener spawns a thread that calls HIToolbox/TSM APIs,
            # which macOS 26 requires on the main dispatch queue (crashes otherwise).
            # CGEventTap fires on the main thread's CFRunLoop (shared with tkinter).
            log.info("macOS: Keyboard monitoring requires Accessibility permission.")
            log.info("macOS: Grant in System Settings > Privacy & Security > Accessibility.")

            mask = 1 << kCGEventFlagsChanged
            self._tap = CGEventTapCreate(
                kCGSessionEventTap,
                kCGHeadInsertEventTap,
                0,  # active tap (can observe + modify events)
                mask,
                self._mac_event_callback,
                None,
            )

            if self._tap is None:
                log.error(
                    "Failed to create event tap - Accessibility permission not granted. "
                    "Open System Settings > Privacy & Security > Accessibility and add Bark."
                )
                return False

            self._tap_source = CFMachPortCreateRunLoopSource(None, self._tap, 0)
            CFRunLoopAddSource(
                CFRunLoopGetMain(), self._tap_source, kCFRunLoopCommonModes
            )
            CGEventTapEnable(self._tap, True)
            log.info("Quartz event tap active (Right Option key).")

        log.info("Keyboard listener started.")
        return True

    def stop(self):
        if self._listener:
            self._listener.stop()
            if IS_WIN:
                self._restore_caps_state()
        if IS_MAC:
            if self._tap_source:
                try:
                    CFRunLoopRemoveSource(
                        CFRunLoopGetMain(), self._tap_source, kCFRunLoopCommonModes
                    )
                except Exception:
                    pass
            if self._tap:
                try:
                    CGEventTapEnable(self._tap, False)
                except Exception:
                    pass
