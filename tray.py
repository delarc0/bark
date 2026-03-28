import logging
import os
import queue
import sys
import threading

from config import cfg, save_config, IS_WIN, IS_MAC
from paths import get_app_dir

log = logging.getLogger(__name__)

_dir = get_app_dir()
ICON_PATH = os.path.join(_dir, "icon.ico")

# Language options: (config value, display name)
LANGUAGES_TOP = [
    (None, "Auto-detect"),
    ("en", "English"),
    ("sv", "Swedish"),
    ("fi", "Finnish"),
    ("es", "Spanish"),
]

LANGUAGES_OTHER = [
    ("fr", "French"),
    ("de", "German"),
    ("no", "Norwegian"),
    ("da", "Danish"),
    ("pt", "Portuguese"),
    ("it", "Italian"),
    ("nl", "Dutch"),
    ("pl", "Polish"),
    ("ja", "Japanese"),
    ("zh", "Chinese"),
    ("ko", "Korean"),
    ("ar", "Arabic"),
]

ALL_LANGUAGES = LANGUAGES_TOP + LANGUAGES_OTHER

# Trigger key options per platform
TRIGGER_KEYS_WIN = [
    ("capslock", "Caps Lock"),
    ("scroll_lock", "Scroll Lock"),
    ("pause", "Pause"),
    ("right_ctrl", "Right Ctrl"),
]

TRIGGER_KEYS_MAC = [
    ("right_option", "Right Option"),
    ("right_command", "Right Command"),
]


# --- macOS menu bar via PyObjC ---
_APPKIT_OK = False
_mac_callbacks = {}  # tag -> callable
_tray_ref = None  # module-level ref for ObjC delegate

if IS_MAC:
    try:
        from AppKit import (
            NSStatusBar,
            NSMenu,
            NSMenuItem,
            NSVariableStatusItemLength,
            NSOnState,
            NSOffState,
            NSImage,
            NSFont,
            NSAttributedString,
            NSColor,
            NSForegroundColorAttributeName,
            NSFontAttributeName,
        )
        from Foundation import NSObject as _NSObj, NSSize

        class _MenuTarget(_NSObj):
            """Receives NSMenuItem actions and dispatches to Python callbacks."""

            def menuAction_(self, sender):
                cb = _mac_callbacks.get(sender.tag())
                if cb:
                    try:
                        cb()
                    except Exception as e:
                        log.error(f"Menu action error: {e}")

        class _MenuDelegate(_NSObj):
            """Refreshes toggle states when the menu opens."""

            def menuNeedsUpdate_(self, menu):
                if _tray_ref:
                    try:
                        _tray_ref._refresh_mac_menu()
                    except Exception as e:
                        log.error(f"Menu refresh error: {e}")

        _APPKIT_OK = True
        log.info("AppKit loaded OK - menu bar icon available.")
    except ImportError as e:
        log.warning(f"AppKit not available for menu bar: {e}. "
                    "Install: pip install pyobjc-framework-Cocoa")


# --- Tag constants for Mac menu items ---
_TAG_OVERLAY = 1
_TAG_SOUND = 2
_TAG_DARK = 3
_TAG_CLIP = 4
_TAG_STREAM = 5
_TAG_STARTUP = 6
_TAG_HISTORY = 7
_TAG_QUIT = 8
_TAG_CUSTOM_WORDS = 9
_TAG_UPDATE = 10
_TAG_LANG = 100    # 100 + index into ALL_LANGUAGES
_TAG_TRIGGER = 200  # 200 + index into TRIGGER_KEYS_MAC


class SystemTray:
    def __init__(self, overlay, on_quit=None):
        self._overlay = overlay
        self._on_quit = on_quit
        self._icon = None  # pystray Icon (unused on Windows now)
        self._status_item = None  # NSStatusItem (Mac)
        self._win32_hwnd = None   # HWND for Win32 tray (Windows)
        self._win32_nid = None    # NOTIFYICONDATAW (Windows)
        self._mac_menu = None
        self._mac_target = None
        self._mac_delegate = None
        self._state = "loading"
        self._update_version = None  # Set when a newer version is available
        # Queue for actions dispatched from ObjC callbacks (NSMenu).
        # Calling _root.after() from inside an NSMenu modal loop crashes
        # Tcl/Cocoa, so ObjC callbacks put work here and the main thread
        # polls it safely via _poll_tray_actions().
        self._action_queue = queue.Queue()

    def _poll_tray_actions(self):
        """Process queued tray menu actions on the main thread."""
        try:
            while True:
                action = self._action_queue.get_nowait()
                try:
                    action()
                except Exception as e:
                    log.error(f"Tray action error: {e}")
        except queue.Empty:
            pass
        self._overlay._root.after(50, self._poll_tray_actions)

    def start(self):
        if IS_MAC:
            if _APPKIT_OK:
                log.info("Scheduling Mac menu bar setup on main thread...")
                self._overlay._root.after(100, self._setup_mac_tray)
                self._overlay._root.after(50, self._poll_tray_actions)
            else:
                log.warning("Mac menu bar skipped (AppKit not available). "
                            "Install: pip install pyobjc-framework-Cocoa")
        else:
            threading.Thread(target=self._run, daemon=True).start()

    def set_state(self, state):
        """Update menu bar icon to reflect app state."""
        self._state = state
        if IS_MAC and self._status_item:
            try:
                self._action_queue.put(self._update_mac_icon)
            except Exception:
                pass

    # ================================================================ macOS NSStatusItem

    def _setup_mac_tray(self):
        global _tray_ref
        _tray_ref = self

        try:
            sb = NSStatusBar.systemStatusBar()
            self._status_item = sb.statusItemWithLength_(NSVariableStatusItemLength)
            if not self._status_item:
                log.error("NSStatusBar returned nil status item.")
                return

            btn = self._status_item.button()
            if not btn:
                log.error("NSStatusItem button is nil.")
                return

            self._mac_target = _MenuTarget.alloc().init()
            self._mac_delegate = _MenuDelegate.alloc().init()

            self._mac_menu = NSMenu.alloc().init()
            self._mac_menu.setAutoenablesItems_(False)
            self._mac_menu.setDelegate_(self._mac_delegate)

            # Load Westie icon for menu bar
            icon_path = os.path.join(_dir, "icon.png")
            if os.path.exists(icon_path):
                img = NSImage.alloc().initWithContentsOfFile_(icon_path)
                if img:
                    img.setSize_(NSSize(18, 18))
                    img.setTemplate_(False)
                    btn.setImage_(img)
                    log.info("Menu bar icon: Westie image loaded")
            else:
                btn.setTitle_("\U0001F415")  # fallback emoji

            self._build_mac_menu()
            self._status_item.setMenu_(self._mac_menu)
            self._update_mac_icon()

            log.info(f"Mac menu bar icon ready. Button frame: {btn.frame()}")

            # Hide Dock icon AFTER status item is created and rendered.
            self._overlay._root.after(500, self._hide_dock_icon)
        except Exception as e:
            log.error(f"Failed to create menu bar icon: {e}", exc_info=True)

    def _hide_dock_icon(self):
        """Switch to Accessory policy to hide the Dock icon."""
        try:
            from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
            NSApplication.sharedApplication().setActivationPolicy_(
                NSApplicationActivationPolicyAccessory
            )
            log.info("Dock icon hidden (Accessory policy, deferred).")
        except Exception as e:
            log.warning(f"Could not hide Dock icon: {e}")

    def _update_mac_icon(self):
        """Set the menu bar status dot color based on current state."""
        if not self._status_item:
            return
        btn = self._status_item.button()
        if not btn:
            return
        try:
            colors = {
                "idle": NSColor.systemGreenColor(),
                "loading": NSColor.systemOrangeColor(),
                "recording": NSColor.systemRedColor(),
                "transcribing": NSColor.systemYellowColor(),
                "done": NSColor.systemGreenColor(),
                "error": NSColor.systemRedColor(),
            }
            color = colors.get(self._state, NSColor.systemGreenColor())
            attrs = {
                NSForegroundColorAttributeName: color,
                NSFontAttributeName: NSFont.systemFontOfSize_(8),
            }
            title = NSAttributedString.alloc().initWithString_attributes_(
                "\u25CF", attrs  # ● solid circle
            )
            btn.setAttributedTitle_(title)
        except Exception as e:
            log.warning(f"Attributed title failed, using plain dot: {e}")
            btn.setTitle_("\u25CF")

    def _build_mac_menu(self):
        """Build the full menu. Called once at setup and rebuilt on refresh."""
        menu = self._mac_menu
        menu.removeAllItems()
        _mac_callbacks.clear()

        # Register callbacks — use the action queue on Mac so ObjC menu
        # callbacks never touch Tcl directly (avoids reentrancy segfault).
        _mac_callbacks[_TAG_OVERLAY] = lambda: self._action_queue.put(
            self._overlay._toggle_show_overlay
        )
        _mac_callbacks[_TAG_SOUND] = self._toggle_sound
        _mac_callbacks[_TAG_DARK] = lambda: self._action_queue.put(
            self._overlay._toggle_dark_mode
        )
        _mac_callbacks[_TAG_CLIP] = lambda: self._action_queue.put(
            self._overlay._toggle_clipboard_mode
        )
        _mac_callbacks[_TAG_STREAM] = self._toggle_streaming
        _mac_callbacks[_TAG_STARTUP] = self._toggle_startup
        _mac_callbacks[_TAG_HISTORY] = self._open_history
        _mac_callbacks[_TAG_CUSTOM_WORDS] = self._open_custom_words
        _mac_callbacks[_TAG_UPDATE] = self._open_update
        _mac_callbacks[_TAG_QUIT] = lambda: self._action_queue.put(self._quit)

        # Show Overlay toggle
        self._add_item(menu, "Show Overlay", _TAG_OVERLAY, checked=cfg["show_overlay"])

        menu.addItem_(NSMenuItem.separatorItem())

        # Toggles
        self._add_item(menu, "Sound", _TAG_SOUND, checked=cfg["sound_enabled"])
        self._add_item(menu, "Dark Mode", _TAG_DARK, checked=cfg["dark_mode"])
        clip_label = "Mode: Clipboard" if cfg["clipboard_mode"] else "Mode: Type"
        self._add_item(menu, clip_label, _TAG_CLIP)
        self._add_item(menu, "Streaming Preview", _TAG_STREAM, checked=cfg["streaming_preview"])

        menu.addItem_(NSMenuItem.separatorItem())

        # Language submenu
        lang_menu = NSMenu.alloc().init()
        lang_menu.setAutoenablesItems_(False)
        for i, (code, name) in enumerate(ALL_LANGUAGES):
            tag = _TAG_LANG + i
            _mac_callbacks[tag] = self._make_language_handler(code)
            item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                name, "menuAction:", ""
            )
            item.setTarget_(self._mac_target)
            item.setTag_(tag)
            if cfg["language"] == code:
                item.setState_(NSOnState)
            lang_menu.addItem_(item)

        lang_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Language", None, ""
        )
        lang_item.setSubmenu_(lang_menu)
        menu.addItem_(lang_item)

        # Trigger key submenu
        trigger_menu = NSMenu.alloc().init()
        trigger_menu.setAutoenablesItems_(False)
        for i, (code, name) in enumerate(TRIGGER_KEYS_MAC):
            tag = _TAG_TRIGGER + i
            _mac_callbacks[tag] = self._make_trigger_handler(code, "trigger_key_mac")
            item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                name, "menuAction:", ""
            )
            item.setTarget_(self._mac_target)
            item.setTag_(tag)
            if cfg["trigger_key_mac"] == code:
                item.setState_(NSOnState)
            trigger_menu.addItem_(item)

        trigger_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Trigger Key", None, ""
        )
        trigger_item.setSubmenu_(trigger_menu)
        menu.addItem_(trigger_item)

        menu.addItem_(NSMenuItem.separatorItem())

        self._add_item(menu, "Start on Login", _TAG_STARTUP, checked=cfg["start_on_login"])
        self._add_item(menu, "History", _TAG_HISTORY)
        self._add_item(menu, "Custom Words", _TAG_CUSTOM_WORDS)
        if self._update_version:
            self._add_item(menu, f"Update Available (v{self._update_version})", _TAG_UPDATE)

        menu.addItem_(NSMenuItem.separatorItem())

        self._add_item(menu, "Quit", _TAG_QUIT)

    def _add_item(self, menu, title, tag, checked=None):
        item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            title, "menuAction:", ""
        )
        item.setTarget_(self._mac_target)
        item.setTag_(tag)
        if checked is not None:
            item.setState_(NSOnState if checked else NSOffState)
        menu.addItem_(item)

    def _refresh_mac_menu(self):
        """Called by delegate when menu is about to open. Rebuild for fresh state."""
        self._build_mac_menu()

    # ================================================================ Windows Win32 tray

    def _run(self):
        """Windows tray icon via direct Win32 Shell_NotifyIconW.

        Bypasses pystray entirely -- ExtractIconW loads the ICO reliably
        (proven by the taskbar icon fix) whereas pystray's PIL-to-HICON
        conversion fails silently on some Windows 11 setups.
        """
        try:
            self._run_win32()
        except Exception as e:
            log.error(f"Win32 tray thread crashed: {e}", exc_info=True)

    def _run_win32(self):
        import ctypes
        import ctypes.wintypes as wt

        _user32 = ctypes.windll.user32
        _shell32 = ctypes.windll.shell32
        _kernel32 = ctypes.windll.kernel32
        _gdi32 = ctypes.windll.gdi32

        # ---- Win32 constants ----
        WM_USER = 0x0400
        WM_TRAYICON = WM_USER + 20
        WM_DESTROY = 0x0002
        WM_COMMAND = 0x0111
        WM_RBUTTONUP = 0x0205
        WM_LBUTTONUP = 0x0202

        NIM_ADD = 0x00
        NIM_MODIFY = 0x01
        NIM_DELETE = 0x02
        NIF_MESSAGE = 0x01
        NIF_ICON = 0x02
        NIF_TIP = 0x04
        NIF_INFO = 0x10

        MF_STRING = 0x0000
        MF_SEPARATOR = 0x0800
        MF_POPUP = 0x0010
        MF_CHECKED = 0x0008

        TPM_LEFTBUTTON = 0x0000
        TPM_RETURNCMD = 0x0100
        TPM_NONOTIFY = 0x0080

        MIM_BACKGROUND = 0x00000002
        MIM_APPLYTOSUBMENUS = 0x80000000

        class MENUINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wt.DWORD),
                ("fMask", wt.DWORD),
                ("dwStyle", wt.DWORD),
                ("cyMax", wt.UINT),
                ("hbrBack", wt.HBRUSH),
                ("dwContextHelpID", wt.DWORD),
                ("dwMenuData", ctypes.POINTER(wt.ULONG)),
            ]

        # Light background brush so black text is readable (COLORREF = 0x00BBGGRR)
        _menu_brush = _gdi32.CreateSolidBrush(0x00F0F0F0)  # RGB(240,240,240)

        def _apply_menu_bg(hmenu):
            mi = MENUINFO()
            mi.cbSize = ctypes.sizeof(MENUINFO)
            mi.fMask = MIM_BACKGROUND | MIM_APPLYTOSUBMENUS
            mi.hbrBack = _menu_brush
            _user32.SetMenuInfo(hmenu, ctypes.byref(mi))

        # ---- NOTIFYICONDATAW ----
        WCHAR = ctypes.c_wchar

        class NOTIFYICONDATAW(ctypes.Structure):
            _fields_ = [
                ("cbSize", wt.DWORD),
                ("hWnd", wt.HWND),
                ("uID", wt.UINT),
                ("uFlags", wt.UINT),
                ("uCallbackMessage", wt.UINT),
                ("hIcon", wt.HICON),
                ("szTip", WCHAR * 128),
                ("dwState", wt.DWORD),
                ("dwStateMask", wt.DWORD),
                ("szInfo", WCHAR * 256),
                ("uVersion", wt.UINT),
                ("szInfoTitle", WCHAR * 64),
                ("dwInfoFlags", wt.DWORD),
            ]

        WNDPROC = ctypes.WINFUNCTYPE(
            ctypes.c_long, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM,
        )

        class WNDCLASSEXW(ctypes.Structure):
            _fields_ = [
                ("cbSize", wt.UINT),
                ("style", wt.UINT),
                ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int),
                ("hInstance", wt.HINSTANCE),
                ("hIcon", wt.HICON),
                ("hCursor", wt.HANDLE),
                ("hbrBackground", wt.HBRUSH),
                ("lpszMenuName", wt.LPCWSTR),
                ("lpszClassName", wt.LPCWSTR),
                ("hIconSm", wt.HICON),
            ]

        # ---- Menu item IDs ----
        _ID_OVERLAY = 1
        _ID_CLIPBOARD = 2
        _ID_SOUND = 3
        _ID_DARK = 4
        _ID_STREAMING = 5
        _ID_STARTUP = 6
        _ID_HISTORY = 7
        _ID_QUIT = 8
        _ID_CUSTOM_WORDS = 9
        _ID_UPDATE = 10
        _ID_LANG_BASE = 100   # 100 + i
        _ID_TRIGGER_BASE = 200  # 200 + i

        # ---- Load icon via ExtractIconW (proven to work) ----
        _shell32.ExtractIconW.restype = ctypes.c_void_p
        hicon = _shell32.ExtractIconW(0, ICON_PATH, 0)
        if not hicon or hicon == 1:
            log.error(f"ExtractIconW failed for tray icon: {ICON_PATH}")
            return
        log.info(f"Tray: ExtractIconW OK ({hicon:#x})")

        # ---- Dispatch map: menu ID -> handler ----
        trigger_keys = TRIGGER_KEYS_WIN
        trigger_cfg_key = "trigger_key_win"
        tray = self  # closure ref

        dispatch = {
            _ID_OVERLAY: self._toggle_overlay,
            _ID_CLIPBOARD: self._toggle_clipboard,
            _ID_SOUND: self._toggle_sound,
            _ID_DARK: self._toggle_dark_mode,
            _ID_STREAMING: self._toggle_streaming,
            _ID_STARTUP: self._toggle_startup,
            _ID_HISTORY: self._open_history,
            _ID_CUSTOM_WORDS: self._open_custom_words,
            _ID_UPDATE: self._open_update,
            _ID_QUIT: self._quit,
        }
        for i, (code, _name) in enumerate(ALL_LANGUAGES):
            dispatch[_ID_LANG_BASE + i] = self._make_language_handler(code)
        for i, (code, _name) in enumerate(trigger_keys):
            dispatch[_ID_TRIGGER_BASE + i] = self._make_trigger_handler(code, trigger_cfg_key)

        # ---- Build popup menu ----
        def _build_menu():
            hmenu = _user32.CreatePopupMenu()

            clip_text = "Mode: Clipboard" if cfg["clipboard_mode"] else "Mode: Type"
            sound_text = "Sound: ON" if cfg["sound_enabled"] else "Sound: OFF"
            dark_text = "Dark Mode: ON" if cfg["dark_mode"] else "Dark Mode: OFF"
            stream_text = "Streaming: ON" if cfg["streaming_preview"] else "Streaming: OFF"
            startup_text = "Start on Login: ON" if cfg["start_on_login"] else "Start on Login: OFF"

            _user32.AppendMenuW(hmenu, MF_STRING, _ID_OVERLAY, "Show/Hide Overlay")
            _user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)
            _user32.AppendMenuW(hmenu, MF_STRING, _ID_CLIPBOARD, clip_text)
            _user32.AppendMenuW(hmenu, MF_STRING, _ID_SOUND, sound_text)
            _user32.AppendMenuW(hmenu, MF_STRING, _ID_DARK, dark_text)
            _user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)

            # Language submenu
            hlang = _user32.CreatePopupMenu()
            for i, (code, name) in enumerate(LANGUAGES_TOP):
                flags = MF_STRING | (MF_CHECKED if cfg["language"] == code else 0)
                _user32.AppendMenuW(hlang, flags, _ID_LANG_BASE + i, name)
            # Others sub-submenu
            hothers = _user32.CreatePopupMenu()
            offset = len(LANGUAGES_TOP)
            for i, (code, name) in enumerate(LANGUAGES_OTHER):
                flags = MF_STRING | (MF_CHECKED if cfg["language"] == code else 0)
                _user32.AppendMenuW(hothers, flags, _ID_LANG_BASE + offset + i, name)
            _user32.AppendMenuW(hlang, MF_POPUP, hothers, "Others")
            _user32.AppendMenuW(hmenu, MF_POPUP, hlang, "Language")

            # Trigger key submenu
            htrigger = _user32.CreatePopupMenu()
            for i, (code, name) in enumerate(trigger_keys):
                flags = MF_STRING | (MF_CHECKED if cfg[trigger_cfg_key] == code else 0)
                _user32.AppendMenuW(htrigger, flags, _ID_TRIGGER_BASE + i, name)
            _user32.AppendMenuW(hmenu, MF_POPUP, htrigger, "Trigger Key")

            _user32.AppendMenuW(hmenu, MF_STRING, _ID_STREAMING, stream_text)
            _user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)
            _user32.AppendMenuW(hmenu, MF_STRING, _ID_STARTUP, startup_text)
            _user32.AppendMenuW(hmenu, MF_STRING, _ID_HISTORY, "History")
            _user32.AppendMenuW(hmenu, MF_STRING, _ID_CUSTOM_WORDS, "Custom Words")
            if tray._update_version:
                _user32.AppendMenuW(hmenu, MF_STRING, _ID_UPDATE,
                                    f"Update Available (v{tray._update_version})")
            _user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)
            _user32.AppendMenuW(hmenu, MF_STRING, _ID_QUIT, "Quit")
            _apply_menu_bg(hmenu)
            return hmenu

        # ---- WndProc ----
        def wnd_proc(hwnd, msg, wparam, lparam):
            if msg == WM_TRAYICON:
                if lparam in (WM_RBUTTONUP, WM_LBUTTONUP):
                    pt = wt.POINT()
                    _user32.GetCursorPos(ctypes.byref(pt))
                    _user32.SetForegroundWindow(hwnd)
                    hmenu = _build_menu()
                    cmd = _user32.TrackPopupMenu(
                        hmenu, TPM_RETURNCMD | TPM_NONOTIFY | TPM_LEFTBUTTON,
                        pt.x, pt.y, 0, hwnd, None,
                    )
                    _user32.DestroyMenu(hmenu)
                    _user32.PostMessageW(hwnd, 0, 0, 0)  # dismiss
                    if cmd and cmd in dispatch:
                        try:
                            dispatch[cmd]()
                        except Exception as e:
                            log.error(f"Tray menu handler error: {e}")
                    return 0
            elif msg == WM_DESTROY:
                if hasattr(tray, "_win32_nid") and tray._win32_nid:
                    _shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(tray._win32_nid))
                _user32.PostQuitMessage(0)
                return 0
            return _user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        # prevent GC of callback
        self._wnd_proc_ref = WNDPROC(wnd_proc)

        # ---- Register window class ----
        hinstance = _kernel32.GetModuleHandleW(None)
        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.lpfnWndProc = self._wnd_proc_ref
        wc.hInstance = hinstance
        wc.lpszClassName = "BarkTrayWnd"

        atom = _user32.RegisterClassExW(ctypes.byref(wc))
        if not atom:
            log.error(f"RegisterClassExW failed: {_kernel32.GetLastError()}")
            return

        # ---- Create hidden window (normal, not message-only) ----
        # TrackPopupMenu + SetForegroundWindow need a real window
        hwnd = _user32.CreateWindowExW(
            0, "BarkTrayWnd", "Bark", 0,
            0, 0, 0, 0,
            None, None, hinstance, None,
        )
        if not hwnd:
            log.error(f"CreateWindowExW failed: {_kernel32.GetLastError()}")
            return

        # ---- Shell_NotifyIconW ----
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = hwnd
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = WM_TRAYICON
        nid.hIcon = ctypes.cast(ctypes.c_void_p(hicon), wt.HICON)
        nid.szTip = "Bark - Voice Dictation"
        self._win32_nid = nid
        self._win32_hwnd = hwnd

        ok = _shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))
        if ok:
            log.info("Shell_NotifyIconW(NIM_ADD) succeeded -- tray icon created")
        else:
            log.error(f"Shell_NotifyIconW(NIM_ADD) failed: {_kernel32.GetLastError()}")
            return

        # ---- Balloon notification ----
        trigger = cfg.get("trigger_key_win", "capslock")
        key_name = {"capslock": "Caps Lock", "scroll_lock": "Scroll Lock",
                     "pause": "Pause", "right_ctrl": "Right Ctrl"}.get(trigger, trigger)
        nid.uFlags = NIF_INFO
        nid.szInfo = f"Hold {key_name} to dictate"
        nid.szInfoTitle = "Bark is running"
        _shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))

        log.info("Win32 tray message loop starting...")

        # ---- Message loop ----
        msg = wt.MSG()
        while _user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            _user32.TranslateMessage(ctypes.byref(msg))
            _user32.DispatchMessageW(ctypes.byref(msg))

        log.info("Win32 tray message loop ended")

    # ================================================================ Menu handlers (shared)

    def _toggle_overlay(self):
        try:
            self._overlay._root.after(0, self._overlay_toggle_safe)
        except Exception:
            pass

    def _overlay_toggle_safe(self):
        if self._overlay._visible:
            self._overlay._hide_overlay()
        else:
            self._overlay.show_overlay()

    def _toggle_clipboard(self):
        try:
            self._overlay._root.after(0, self._overlay._toggle_clipboard_mode)
        except Exception:
            pass

    def _toggle_sound(self):
        cfg["sound_enabled"] = not cfg["sound_enabled"]
        save_config()

    def _toggle_dark_mode(self):
        try:
            self._overlay._root.after(0, self._overlay._toggle_dark_mode)
        except Exception:
            pass

    def _toggle_streaming(self):
        cfg["streaming_preview"] = not cfg["streaming_preview"]
        save_config()

    def _make_language_handler(self, code):
        def handler():
            cfg["language"] = code
            save_config()
            log.info(f"Language set to: {code or 'auto-detect'}")
        return handler

    def _make_trigger_handler(self, code, cfg_key):
        def handler():
            cfg[cfg_key] = code
            save_config()
            log.info(f"Trigger key changed to '{code}' - restart Bark to apply.")
        return handler

    def _toggle_startup(self):
        cfg["start_on_login"] = not cfg["start_on_login"]
        save_config()
        try:
            if cfg["start_on_login"]:
                _enable_startup()
            else:
                _disable_startup()
        except Exception as e:
            log.warning(f"Failed to update startup setting: {e}")

    def _open_history(self):
        from history import open_history
        open_history()

    def _open_custom_words(self):
        from transcriber import CUSTOM_WORDS_PATH
        if not os.path.exists(CUSTOM_WORDS_PATH):
            try:
                with open(CUSTOM_WORDS_PATH, "w", encoding="utf-8") as f:
                    f.write("# One word or phrase per line\n# These help Whisper recognize custom terms\n# Example:\n# Kubernetes\n# Lab37\n")
            except Exception as e:
                log.warning(f"Failed to create custom_words.txt: {e}")
                return
        try:
            if IS_WIN:
                os.startfile(CUSTOM_WORDS_PATH)
            else:
                import subprocess
                subprocess.Popen(["open", CUSTOM_WORDS_PATH])
        except Exception as e:
            log.warning(f"Failed to open custom_words.txt: {e}")

    def show_update(self, version: str):
        """Notify user that a newer version is available."""
        self._update_version = version
        if IS_WIN and self._win32_nid:
            import ctypes
            NIF_INFO = 0x10
            NIM_MODIFY = 0x01
            self._win32_nid.uFlags = NIF_INFO
            self._win32_nid.szInfo = f"Version {version} is available"
            self._win32_nid.szInfoTitle = "Bark Update"
            ctypes.windll.shell32.Shell_NotifyIconW(
                NIM_MODIFY, ctypes.byref(self._win32_nid)
            )

    def _open_update(self):
        import webbrowser
        webbrowser.open("https://github.com/delarc0/bark/releases/latest")

    def _quit(self):
        if self._on_quit:
            try:
                self._on_quit()
            except Exception:
                pass
        if IS_WIN and self._win32_hwnd:
            import ctypes
            ctypes.windll.user32.DestroyWindow(self._win32_hwnd)
        elif self._icon:
            self._icon.stop()
        if IS_MAC:
            # On Mac, _quit runs on the main thread via _action_queue,
            # so we can call overlay.quit() directly (it touches Tcl).
            try:
                self._overlay.quit()
            except Exception:
                pass

    def stop(self):
        if IS_WIN and self._win32_hwnd:
            import ctypes
            ctypes.windll.user32.DestroyWindow(self._win32_hwnd)
            self._win32_hwnd = None
        elif self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass
        if IS_MAC and self._status_item:
            try:
                NSStatusBar.systemStatusBar().removeStatusItem_(self._status_item)
                self._status_item = None
            except Exception:
                pass


# --- Startup on login ---

def _enable_startup():
    if IS_WIN:
        _win_set_startup(True)
    elif IS_MAC:
        _mac_set_startup(True)


def _disable_startup():
    if IS_WIN:
        _win_set_startup(False)
    elif IS_MAC:
        _mac_set_startup(False)


def _win_set_startup(enable: bool):
    import winreg
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
        if enable:
            if getattr(sys, "frozen", False):
                # Frozen mode: Bark.exe is the entry point
                winreg.SetValueEx(key, "Bark", 0, winreg.REG_SZ, f'"{sys.executable}"')
            else:
                # Dev mode: use pythonw.exe to run without console window
                app_path = os.path.join(_dir, "dictation.py")
                pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
                if not os.path.exists(pythonw):
                    pythonw = sys.executable
                winreg.SetValueEx(key, "Bark", 0, winreg.REG_SZ, f'"{pythonw}" "{app_path}"')
            log.info("Added Bark to Windows startup.")
        else:
            try:
                winreg.DeleteValue(key, "Bark")
                log.info("Removed Bark from Windows startup.")
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except Exception as e:
        log.warning(f"Failed to update Windows startup: {e}")


def _mac_set_startup(enable: bool):
    plist_dir = os.path.expanduser("~/Library/LaunchAgents")
    plist_path = os.path.join(plist_dir, "com.lab37.bark.plist")

    if enable:
        app_path = os.path.join(_dir, "dictation.py")
        python = sys.executable
        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.lab37.bark</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python}</string>
        <string>{app_path}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
"""
        try:
            os.makedirs(plist_dir, exist_ok=True)
            with open(plist_path, "w") as f:
                f.write(plist_content)
            log.info("Added Bark to macOS login items.")
        except Exception as e:
            log.warning(f"Failed to create LaunchAgent: {e}")
    else:
        try:
            os.remove(plist_path)
            log.info("Removed Bark from macOS login items.")
        except FileNotFoundError:
            pass
        except Exception as e:
            log.warning(f"Failed to remove LaunchAgent: {e}")
