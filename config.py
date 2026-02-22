import json
import logging
import os
import sys
import tempfile

log = logging.getLogger(__name__)

# Platform detection (not configurable)
IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"

# Config file lives next to the app
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(_APP_DIR, "bark_config.json")

DEFAULT_CONFIG = {
    # Model
    "language": None,           # None = auto-detect
    "beam_size": 5,
    # Audio
    "sample_rate": 16000,
    "min_audio_duration": 0.3,
    "pre_buffer": 0.5,
    "auto_stop": True,
    "silence_timeout": 1.5,
    # Feedback
    "beep_volume": 0.3,
    "sound_enabled": True,
    # Typing
    "paste_delay": 0.15,
    "clipboard_mode": False,
    # Overlay
    "dark_mode": False,
    "show_overlay": not IS_MAC,  # Mac: tray-only by default; Windows: overlay
    "overlay_x": None,
    "overlay_y": None,
    "idle_timeout": 8,          # seconds before pill fades out (0 = never)
    # Trigger key
    "trigger_key_win": "capslock",
    "trigger_key_mac": "right_option",
    # Startup
    "start_on_login": False,
    "first_run": True,
    # Streaming preview
    "streaming_preview": False,
    # Version
    "version": "1.2.0",
}


def load_config() -> dict:
    config = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
            config.update(saved)
        except Exception as e:
            log.warning(f"Failed to load config: {e}")
    return config


def save_config(config=None):
    if config is None:
        config = cfg
    try:
        fd, tmp = tempfile.mkstemp(
            dir=os.path.dirname(CONFIG_PATH), suffix=".tmp"
        )
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        os.replace(tmp, CONFIG_PATH)
    except Exception as e:
        log.warning(f"Failed to save config: {e}")
        try:
            os.unlink(tmp)
        except Exception:
            pass


# Live config -- imported by all modules
cfg = load_config()

# Platform-specific model constants (not user-configurable)
if IS_MAC:
    MODEL_SIZE = "mlx-community/whisper-large-v3-turbo"
    DEVICE = "mlx"
    COMPUTE_TYPE = None
else:
    MODEL_SIZE = "deepdml/faster-whisper-large-v3-turbo-ct2"
    DEVICE = "cuda"
    COMPUTE_TYPE = "float16"

# Virtual key codes (platform-fixed)
if IS_WIN:
    VK_CAPITAL = 0x14

# Trigger key display name
_KEY_NAMES = {
    "capslock": "Caps Lock",
    "scroll_lock": "Scroll Lock",
    "pause": "Pause",
    "right_ctrl": "Right Ctrl",
    "right_option": "Right Option",
    "right_command": "Right Command",
}
TRIGGER_KEY_NAME = _KEY_NAMES.get(
    cfg["trigger_key_win"] if IS_WIN else cfg["trigger_key_mac"], "Unknown"
)

# Convenience aliases for constants used everywhere
SAMPLE_RATE = cfg["sample_rate"]
CHANNELS = 1
DTYPE = "float32"
