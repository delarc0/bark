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


class SystemTray:
    def __init__(self, overlay, on_quit=None):
        self._overlay = overlay
        self._on_quit = on_quit
        self._icon = None

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

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

    # --- Menu handlers ---

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
        # Delegate to overlay (handles config + UI update on main thread)
        try:
            self._overlay._root.after(0, self._overlay._toggle_clipboard_mode)
        except Exception:
            pass

    def _toggle_sound(self):
        cfg["sound_enabled"] = not cfg["sound_enabled"]
        save_config()

    def _toggle_dark_mode(self):
        # Delegate to overlay (handles config + theme update on main thread)
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

    def stop(self):
        if self._icon:
            try:
                self._icon.stop()
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
