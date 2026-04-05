"""Path helpers for frozen (PyInstaller) and dev mode."""

import os
import sys

_FROZEN = getattr(sys, "frozen", False)
_IS_WIN = sys.platform == "win32"


def get_app_dir():
    """Directory containing bundled resources (icon.ico, VERSION, etc.).

    Frozen: PyInstaller's _MEIPASS (_internal/ folder).
    Dev: directory containing this script.
    """
    if _FROZEN:
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def get_data_dir():
    """Directory for user-writable files (config, history, logs, lock).

    Frozen: directory containing Bark.exe (%LOCALAPPDATA%\\Bark).
    Dev: directory containing this script.
    """
    if _FROZEN:
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def open_file(path):
    """Open a file in the OS default application."""
    if _IS_WIN:
        os.startfile(path)
    else:
        import subprocess
        subprocess.Popen(["open", path])
