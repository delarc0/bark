import json
import logging
import os
import sys
import tempfile

from paths import get_app_dir, get_data_dir

log = logging.getLogger(__name__)

# Platform detection (not configurable)
IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"

# Resource dir (bundled read-only files: VERSION, icons)
_APP_DIR = get_app_dir()
# Data dir (writable user files: config, history, logs)
_DATA_DIR = get_data_dir()
CONFIG_PATH = os.path.join(_DATA_DIR, "bark_config.json")

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
    "dark_mode": True,
    "show_overlay": True,  # Pill overlay visible by default; hide via tray menu
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
    # Version (read from VERSION file, this is the fallback)
    "version": "1.4.0",
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
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(
            dir=os.path.dirname(CONFIG_PATH), suffix=".tmp"
        )
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        os.replace(tmp, CONFIG_PATH)
    except Exception as e:
        log.warning(f"Failed to save config: {e}")
        if tmp:
            try:
                os.unlink(tmp)
            except Exception:
                pass


# Live config -- imported by all modules
cfg = load_config()

# Read version from VERSION file (single source of truth for batch scripts too)
_version_file = os.path.join(_APP_DIR, "VERSION")
if os.path.exists(_version_file):
    try:
        with open(_version_file, "r") as f:
            _ver = f.read().strip()
        if _ver:
            cfg["version"] = _ver
    except Exception:
        pass

# Platform-specific model constants (not user-configurable)
if IS_MAC:
    MODEL_SIZE = "mlx-community/whisper-large-v3-turbo"
    DEVICE = "mlx"
    COMPUTE_TYPE = None
else:
    MODEL_SIZE = "deepdml/faster-whisper-large-v3-turbo-ct2"
    # Detect CUDA via the NVIDIA driver DLL (nvcuda.dll).  This avoids
    # depending on torch CUDA libraries which add ~3 GB to the bundle.
    # CTranslate2 (faster-whisper) ships its own CUDA libs separately.
    def _query_nvidia_smi(query="name,driver_version"):
        try:
            import subprocess
            r = subprocess.run(
                ["nvidia-smi", f"--query-gpu={query}", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip().split("\n")[0]
        except Exception:
            pass
        return None

    _cuda_ok = False
    try:
        import ctypes as _ct
        _ct.cdll.LoadLibrary("nvcuda")
        _cuda_ok = True
    except Exception:
        pass
    if _cuda_ok:
        DEVICE = "cuda"
        COMPUTE_TYPE = "float16"
        _gpu_name = _query_nvidia_smi("name")
        log.info(f"CUDA available{': ' + _gpu_name if _gpu_name else ''}")
    else:
        DEVICE = "cpu"
        COMPUTE_TYPE = "int8"
        _diag = ["CUDA not available - using CPU mode (slower transcription)"]
        _smi_out = _query_nvidia_smi()
        if _smi_out:
            _diag.append(f"  nvidia-smi: {_smi_out}")
            _diag.append("  GPU exists but nvcuda.dll not loadable.")
        else:
            _diag.append("  nvidia-smi: not found or no output")
        for _line in _diag:
            log.warning(_line)

# Virtual key codes (Windows)
if IS_WIN:
    VK_CAPITAL = 0x14
    VK_CODES = {
        "capslock": 0x14,      # VK_CAPITAL
        "scroll_lock": 0x91,   # VK_SCROLL
        "pause": 0x13,         # VK_PAUSE
        "right_ctrl": 0xA3,    # VK_RCONTROL
    }

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
