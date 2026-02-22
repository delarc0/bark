import logging
import os
import threading

from config import cfg, save_config, IS_WIN, IS_MAC

log = logging.getLogger(__name__)

_dir = os.path.dirname(os.path.abspath(__file__))
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
        import objc
        from AppKit import (
            NSStatusBar,
            NSMenu,
            NSMenuItem,
            NSVariableStatusItemLength,
            NSFont,
            NSAttributedString,
            NSColor,
            NSOnState,
            NSOffState,
            NSForegroundColorAttributeName,
            NSFontAttributeName,
        )
        from Foundation import NSObject as _NSObj

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
    except ImportError as e:
        log.info(f"AppKit not available for menu bar: {e}")


# --- Tag constants for Mac menu items ---
_TAG_OVERLAY = 1
_TAG_SOUND = 2
_TAG_DARK = 3
_TAG_CLIP = 4
_TAG_STREAM = 5
_TAG_STARTUP = 6
_TAG_HISTORY = 7
_TAG_QUIT = 8
_TAG_LANG = 100    # 100 + index into ALL_LANGUAGES
_TAG_TRIGGER = 200  # 200 + index into TRIGGER_KEYS_MAC


class SystemTray:
    def __init__(self, overlay, on_quit=None):
        self._overlay = overlay
        self._on_quit = on_quit
        self._icon = None  # pystray Icon (Windows)
        self._status_item = None  # NSStatusItem (Mac)
        self._mac_menu = None
        self._mac_target = None
        self._mac_delegate = None
        self._state = "loading"

    def start(self):
        if IS_MAC:
            if _APPKIT_OK:
                # NSStatusItem must be created on the main thread (AppKit requirement)
                self._overlay._root.after(100, self._setup_mac_tray)
            else:
                log.info("Mac menu bar skipped (AppKit not available).")
        else:
            threading.Thread(target=self._run, daemon=True).start()

    def set_state(self, state):
        """Update menu bar icon to reflect app state."""
        self._state = state
        if IS_MAC and self._status_item:
            try:
                self._overlay._root.after(0, self._update_mac_icon)
            except Exception:
                pass

    # ================================================================ macOS NSStatusItem

    def _setup_mac_tray(self):
        global _tray_ref
        _tray_ref = self

        try:
            sb = NSStatusBar.systemStatusBar()
            self._status_item = sb.statusItemWithLength_(NSVariableStatusItemLength)

            self._mac_target = _MenuTarget.alloc().init()
            self._mac_delegate = _MenuDelegate.alloc().init()

            self._mac_menu = NSMenu.alloc().init()
            self._mac_menu.setAutoenablesItems_(False)
            self._mac_menu.setDelegate_(self._mac_delegate)

            self._build_mac_menu()
            self._status_item.setMenu_(self._mac_menu)
            self._update_mac_icon()

            log.info("Mac menu bar icon ready.")
        except Exception as e:
            log.error(f"Failed to create menu bar icon: {e}", exc_info=True)

    def _update_mac_icon(self):
        """Set the menu bar dot color based on current state."""
        if not self._status_item:
            return

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
            NSFontAttributeName: NSFont.systemFontOfSize_(12),
        }
        title = NSAttributedString.alloc().initWithString_attributes_(
            "\u25CF", attrs  # ● solid circle
        )
        self._status_item.button().setAttributedTitle_(title)

    def _build_mac_menu(self):
        """Build the full menu. Called once at setup and rebuilt on refresh."""
        menu = self._mac_menu
        menu.removeAllItems()
        _mac_callbacks.clear()

        # Register callbacks
        _mac_callbacks[_TAG_OVERLAY] = self._toggle_overlay_from_menu
        _mac_callbacks[_TAG_SOUND] = self._toggle_sound
        _mac_callbacks[_TAG_DARK] = lambda: self._overlay._root.after(
            0, self._overlay._toggle_dark_mode
        )
        _mac_callbacks[_TAG_CLIP] = lambda: self._overlay._root.after(
            0, self._overlay._toggle_clipboard_mode
        )
        _mac_callbacks[_TAG_STREAM] = self._toggle_streaming
        _mac_callbacks[_TAG_STARTUP] = self._toggle_startup
        _mac_callbacks[_TAG_HISTORY] = self._open_history
        _mac_callbacks[_TAG_QUIT] = self._quit

        # Show/Hide Overlay
        self._add_item(menu, "Show Overlay" if not self._overlay._visible else "Hide Overlay", _TAG_OVERLAY)

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

    def _toggle_overlay_from_menu(self):
        try:
            if self._overlay._visible:
                self._overlay._root.after(0, self._overlay._hide_overlay)
            else:
                self._overlay._root.after(0, self._overlay.show_overlay)
        except Exception:
            pass

    # ================================================================ Windows pystray

    def _run(self):
        try:
            import pystray
            from PIL import Image
        except ImportError as e:
            log.warning(f"System tray not available (missing pystray/Pillow): {e}")
            return

        try:
            image = Image.open(ICON_PATH)
        except Exception as e:
            log.warning(f"Failed to load tray icon: {e}")
            image = Image.new("RGB", (64, 64), "#42FC93")

        trigger_keys = TRIGGER_KEYS_WIN if IS_WIN else TRIGGER_KEYS_MAC
        trigger_cfg_key = "trigger_key_win" if IS_WIN else "trigger_key_mac"

        menu = pystray.Menu(
            pystray.MenuItem(
                "Show/Hide Overlay",
                self._toggle_overlay,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                lambda item: f"Mode: {'Clipboard' if cfg['clipboard_mode'] else 'Type'}",
                self._toggle_clipboard,
            ),
            pystray.MenuItem(
                lambda item: f"Sound: {'ON' if cfg['sound_enabled'] else 'OFF'}",
                self._toggle_sound,
            ),
            pystray.MenuItem(
                lambda item: f"Dark Mode: {'ON' if cfg['dark_mode'] else 'OFF'}",
                self._toggle_dark_mode,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Language",
                pystray.Menu(
                    *[
                        pystray.MenuItem(
                            name,
                            self._make_language_handler(code),
                            checked=lambda item, c=code: cfg["language"] == c,
                            radio=True,
                        )
                        for code, name in LANGUAGES_TOP
                    ],
                    pystray.MenuItem(
                        "Others",
                        pystray.Menu(
                            *[
                                pystray.MenuItem(
                                    name,
                                    self._make_language_handler(code),
                                    checked=lambda item, c=code: cfg["language"] == c,
                                    radio=True,
                                )
                                for code, name in LANGUAGES_OTHER
                            ]
                        ),
                    ),
                ),
            ),
            pystray.MenuItem(
                "Trigger Key",
                pystray.Menu(
                    *[
                        pystray.MenuItem(
                            name,
                            self._make_trigger_handler(code, trigger_cfg_key),
                            checked=lambda item, c=code: cfg[trigger_cfg_key] == c,
                            radio=True,
                        )
                        for code, name in trigger_keys
                    ]
                ),
            ),
            pystray.MenuItem(
                lambda item: f"Streaming Preview: {'ON' if cfg['streaming_preview'] else 'OFF'}",
                self._toggle_streaming,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                lambda item: f"Start on Login: {'ON' if cfg['start_on_login'] else 'OFF'}",
                self._toggle_startup,
            ),
            pystray.MenuItem(
                "History",
                self._open_history,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Quit",
                self._quit,
            ),
        )

        self._icon = pystray.Icon("Bark", image, "Bark", menu)
        log.info("System tray started.")
        self._icon.run()

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

    def _quit(self):
        if self._on_quit:
            try:
                self._on_quit()
            except Exception:
                pass
        if self._icon:
            self._icon.stop()
        if IS_MAC:
            try:
                self._overlay._root.after(0, self._overlay.quit)
            except Exception:
                pass

    def stop(self):
        if self._icon:
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
            # Use pythonw.exe to run without console window
            app_path = os.path.join(_dir, "dictation.py")
            pythonw = os.path.join(os.path.dirname(os.sys.executable), "pythonw.exe")
            if not os.path.exists(pythonw):
                pythonw = os.sys.executable
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
        python = os.sys.executable
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
