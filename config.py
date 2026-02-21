import sys

# Platform detection
IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"

# Model
if IS_MAC:
    MODEL_SIZE = "mlx-community/whisper-large-v3-turbo"
    DEVICE = "mlx"
    COMPUTE_TYPE = None
else:
    MODEL_SIZE = "deepdml/faster-whisper-large-v3-turbo-ct2"  # ~1.5GB, 6-8x faster than large-v3
    DEVICE = "cuda"
    COMPUTE_TYPE = "float16"

LANGUAGE = None  # None = auto-detect (Swedish, English, etc.)
BEAM_SIZE = 5

# Audio
SAMPLE_RATE = 16000  # Whisper expects 16kHz
CHANNELS = 1
DTYPE = "float32"
MIN_AUDIO_DURATION = 0.3  # Ignore accidental taps shorter than this (seconds)
PRE_BUFFER = 0.5  # Seconds of audio to keep before recording starts (prevents first words being cut off)

# Auto-stop
AUTO_STOP = True  # Auto-stop recording after silence is detected
SILENCE_TIMEOUT = 1.5  # Seconds of silence before auto-stop

# Feedback volume (0.0 - 1.0)
BEEP_VOLUME = 0.3

# Clipboard paste delay (seconds) - increase if paste doesn't work in some apps
PASTE_DELAY = 0.15

# Trigger key
if IS_WIN:
    VK_CAPITAL = 0x14  # Caps Lock virtual key code (Windows)
TRIGGER_KEY_NAME = "Caps Lock" if IS_WIN else "Right Option"

# Logging
LOG_FILE = "dictation.log"
