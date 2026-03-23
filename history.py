import logging
import os
from datetime import datetime

from config import IS_WIN
from paths import get_data_dir

log = logging.getLogger(__name__)

_DATA_DIR = get_data_dir()
HISTORY_PATH = os.path.join(_DATA_DIR, "bark_history.txt")
_HISTORY_OLD = os.path.join(_DATA_DIR, "bark_history.old.txt")
_MAX_HISTORY_BYTES = 1_000_000  # 1 MB


def _rotate_if_needed():
    """Rotate history file when it exceeds _MAX_HISTORY_BYTES."""
    try:
        if os.path.exists(HISTORY_PATH) and os.path.getsize(HISTORY_PATH) > _MAX_HISTORY_BYTES:
            if os.path.exists(_HISTORY_OLD):
                os.remove(_HISTORY_OLD)
            os.rename(HISTORY_PATH, _HISTORY_OLD)
    except Exception as e:
        log.warning(f"History rotation failed: {e}")


def append_history(text: str):
    try:
        _rotate_if_needed()
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
