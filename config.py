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
    "version": "1.3.1",
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
    # Detect CUDA at runtime - fall back to CPU if unavailable
    try:
        import torch
        _cuda_ok = torch.cuda.is_available()
    except Exception as _e:
        _cuda_ok = False
        log.warning(f"PyTorch import or CUDA check failed: {_e}")
    if _cuda_ok:
        DEVICE = "cuda"
        COMPUTE_TYPE = "float16"
        log.info(f"CUDA available: {torch.cuda.get_device_name(0)}")
    else:
        DEVICE = "cpu"
        COMPUTE_TYPE = "int8"
        # Log diagnostics to help debug GPU detection issues remotely
        _diag = ["CUDA not available - using CPU mode (slower transcription)"]
        try:
            _diag.append(f"  PyTorch version: {torch.__version__}")
            _diag.append(f"  PyTorch CUDA build: {torch.version.cuda or 'None (CPU-only build)'}")
        except Exception:
            _diag.append("  Could not read PyTorch version info")
        try:
            import subprocess
            _smi = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=5,
            )
            if _smi.returncode == 0 and _smi.stdout.strip():
                _diag.append(f"  nvidia-smi: {_smi.stdout.strip()}")
                _diag.append("  GPU exists but CUDA is not working in Python.")
                _diag.append("  Fix: update NVIDIA drivers or reinstall with setup-win.bat")
            else:
                _diag.append("  nvidia-smi: not found or no output")
        except Exception:
            _diag.append("  nvidia-smi: not reachable")
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
