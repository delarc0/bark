import logging
import os
from datetime import datetime

from config import IS_WIN

log = logging.getLogger(__name__)

_APP_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_PATH = os.path.join(_APP_DIR, "bark_history.txt")


def append_history(text: str):
    try:
        with open(HISTORY_PATH, "a", encoding="utf-8") as f:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{ts}] {text}\n")
    except Exception as e:
        log.warning(f"Failed to write history: {e}")


def open_history():
    if not os.path.exists(HISTORY_PATH):
        return
    try:
        if IS_WIN:
            os.startfile(HISTORY_PATH)
        else:
            import subprocess
            subprocess.Popen(["open", HISTORY_PATH])
    except Exception as e:
        log.warning(f"Failed to open history: {e}")
