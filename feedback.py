import logging
import math
import os
import subprocess
import tempfile
import wave

import numpy as np
from config import cfg, IS_MAC

log = logging.getLogger(__name__)

SAMPLE_RATE = 44100


def _make_samples(samples: list[float]) -> np.ndarray:
    """Convert float samples [-1, 1] to numpy array for playback."""
    return np.array(samples, dtype=np.float32)


def _generate_pop(freq: int, duration_ms: int, volume: float) -> np.ndarray:
    """Soft pop with exponential decay and 2nd harmonic for warmth."""
    n = int(SAMPLE_RATE * duration_ms / 1000)
    samples = []
    for i in range(n):
        t = i / SAMPLE_RATE
        env = math.exp(-t * 40)
        s = math.sin(2 * math.pi * freq * t)
        s += 0.25 * math.sin(2 * math.pi * freq * 2 * t)
        samples.append(volume * env * s)
    return _make_samples(samples)


def _generate_warm_chime(volume: float) -> np.ndarray:
    """Gentle two-note ascending chime with exponential decay."""
    freqs = [440, 554]  # A4 -> C#5 (major third)
    note_ms = 70
    gap_ms = 20
    n_note = int(SAMPLE_RATE * note_ms / 1000)
    n_gap = int(SAMPLE_RATE * gap_ms / 1000)

    samples = []
    for idx, freq in enumerate(freqs):
        for i in range(n_note):
            t = i / SAMPLE_RATE
            env = math.exp(-t * 25)
            s = math.sin(2 * math.pi * freq * t)
            s += 0.25 * math.sin(2 * math.pi * freq * 2 * t)
            samples.append(volume * env * s)
        if idx == 0:
            samples.extend([0.0] * n_gap)

    return _make_samples(samples)


# Pre-generate tones at import time
_TONE_START = _generate_pop(380, 55, cfg["beep_volume"] * 0.5)
_TONE_DONE = _generate_warm_chime(cfg["beep_volume"] * 0.4)


def _save_wav(data: np.ndarray, path: str):
    """Save float32 numpy array as 16-bit WAV."""
    pcm = (data * 32767).astype(np.int16)
    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm.tobytes())


if IS_MAC:
    # sounddevice.play() crashes Python 3.14 with GIL errors in PortAudio's
    # internal audio thread. Use macOS built-in afplay instead.
    _wav_dir = tempfile.mkdtemp(prefix="bark_beeps_")
    _WAV_START = os.path.join(_wav_dir, "start.wav")
    _WAV_DONE = os.path.join(_wav_dir, "done.wav")
    _save_wav(_TONE_START, _WAV_START)
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
        pass

    def beep_done():
        if cfg["sound_enabled"]:
            _play_mac(_WAV_DONE)

else:
    import sounddevice as sd

    def _play_async(data: np.ndarray):
        try:
            sd.play(data, samplerate=SAMPLE_RATE, blocking=False)
        except Exception as e:
            log.warning(f"Beep failed: {e}")

    def beep_start():
        if cfg["sound_enabled"]:
            _play_async(_TONE_START)

    def beep_stop():
        pass

    def beep_done():
        if cfg["sound_enabled"]:
            _play_async(_TONE_DONE)
