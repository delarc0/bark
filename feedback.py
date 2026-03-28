import logging
import math
import os
import subprocess
import tempfile
import wave

import numpy as np
from config import cfg, IS_MAC

log = logging.getLogger(__name__)

_BEEP_RATE = 44100


def _make_samples(samples: list[float]) -> np.ndarray:
    """Convert float samples [-1, 1] to numpy array for playback."""
    return np.array(samples, dtype=np.float32)


def _generate_rising_chirp(volume: float) -> np.ndarray:
    """Quick rising frequency sweep -- clearly 'starting', not a system click."""
    duration_ms = 80
    f_start, f_end = 480, 880
    n = int(_BEEP_RATE * duration_ms / 1000)
    samples = []
    for i in range(n):
        t = i / _BEEP_RATE
        progress = i / n
        freq = f_start + (f_end - f_start) * progress
        env = math.sin(math.pi * progress)  # smooth fade in/out
        s = math.sin(2 * math.pi * freq * t)
        samples.append(volume * env * s)
    return _make_samples(samples)


def _generate_falling_boop(volume: float) -> np.ndarray:
    """Short descending tone -- a gentle 'done' that doesn't sound like a system click."""
    duration_ms = 100
    f_start, f_end = 660, 440
    n = int(_BEEP_RATE * duration_ms / 1000)
    samples = []
    for i in range(n):
        t = i / _BEEP_RATE
        progress = i / n
        freq = f_start + (f_end - f_start) * progress
        env = 1.0 - progress  # linear fade out
        s = math.sin(2 * math.pi * freq * t)
        samples.append(volume * env * s)
    return _make_samples(samples)


def _generate_tick(volume: float) -> np.ndarray:
    """Short neutral tick -- confirms recording stopped, processing begins."""
    duration_ms = 50
    freq = 550
    n = int(_BEEP_RATE * duration_ms / 1000)
    samples = []
    for i in range(n):
        t = i / _BEEP_RATE
        progress = i / n
        env = 1.0 - progress  # quick linear fade
        s = math.sin(2 * math.pi * freq * t)
        samples.append(volume * env * s)
    return _make_samples(samples)


# Pre-generate tones at import time
_TONE_START = _generate_rising_chirp(cfg["beep_volume"] * 0.45)
_TONE_STOP = _generate_tick(cfg["beep_volume"] * 0.35)
_TONE_DONE = _generate_falling_boop(cfg["beep_volume"] * 0.35)


def _save_wav(data: np.ndarray, path: str):
    """Save float32 numpy array as 16-bit WAV."""
    pcm = (data * 32767).astype(np.int16)
    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(_BEEP_RATE)
        wf.writeframes(pcm.tobytes())


if IS_MAC:
    # sounddevice.play() crashes Python 3.14 with GIL errors in PortAudio's
    # internal audio thread. Use macOS built-in afplay instead.
    _wav_dir = tempfile.mkdtemp(prefix="bark_beeps_")
    _WAV_START = os.path.join(_wav_dir, "start.wav")
    _WAV_STOP = os.path.join(_wav_dir, "stop.wav")
    _WAV_DONE = os.path.join(_wav_dir, "done.wav")
    _save_wav(_TONE_START, _WAV_START)
    _save_wav(_TONE_STOP, _WAV_STOP)
    _save_wav(_TONE_DONE, _WAV_DONE)

    def _play_mac(path: str):
        try:
            subprocess.Popen(
                ["afplay", path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            log.warning(f"Beep failed: {e}")

    def beep_start():
        if cfg["sound_enabled"]:
            _play_mac(_WAV_START)

    def beep_stop():
        if cfg["sound_enabled"]:
            _play_mac(_WAV_STOP)

    def beep_done():
        if cfg["sound_enabled"]:
            _play_mac(_WAV_DONE)

else:
    import sounddevice as sd

    def _play_async(data: np.ndarray):
        try:
            sd.play(data, samplerate=_BEEP_RATE, blocking=False)
        except Exception as e:
            log.warning(f"Beep failed: {e}")

    def beep_start():
        if cfg["sound_enabled"]:
            _play_async(_TONE_START)

    def beep_stop():
        if cfg["sound_enabled"]:
            _play_async(_TONE_STOP)

    def beep_done():
        if cfg["sound_enabled"]:
            _play_async(_TONE_DONE)
