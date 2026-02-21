import logging
import math
import os
import subprocess
import tempfile
import wave

import numpy as np
from config import BEEP_VOLUME, IS_MAC

log = logging.getLogger(__name__)

SAMPLE_RATE = 44100


def _make_samples(samples: list[float]) -> np.ndarray:
    """Convert float samples [-1, 1] to numpy array for playback."""
    return np.array(samples, dtype=np.float32)


def _generate_blip(freq_start: int, freq_end: int, duration_ms: int, volume: float) -> np.ndarray:
    """Short frequency sweep with fast fade - subtle terminal blip."""
    n = int(SAMPLE_RATE * duration_ms / 1000)
    fade = min(n // 3, 100)
    samples = []
    for i in range(n):
        t = i / SAMPLE_RATE
        freq = freq_start + (freq_end - freq_start) * (i / n)
        phase = 2 * math.pi * freq * t
        s = volume * math.sin(phase)
        if i < fade:
            s *= i / fade
        elif i > n - fade:
            s *= (n - i) / fade
        samples.append(s)
    return _make_samples(samples)


def _generate_chime(volume: float) -> np.ndarray:
    """Two-tone ascending chime - soft game notification."""
    note1_freq, note2_freq = 660, 990  # E5 -> B5 (pleasant interval)
    note_ms = 50
    gap_ms = 15
    n_note = int(SAMPLE_RATE * note_ms / 1000)
    n_gap = int(SAMPLE_RATE * gap_ms / 1000)
    fade = min(n_note // 3, 80)

    samples = []
    for freq in [note1_freq, note2_freq]:
        for i in range(n_note):
            t = i / SAMPLE_RATE
            s = volume * math.sin(2 * math.pi * freq * t)
            if i < fade:
                s *= i / fade
            elif i > n_note - fade:
                s *= (n_note - i) / fade
            samples.append(s)
        if freq == note1_freq:
            samples.extend([0.0] * n_gap)

    return _make_samples(samples)


# Pre-generate tones at import time
_TONE_START = _generate_blip(600, 900, 35, BEEP_VOLUME * 0.6)
_TONE_DONE = _generate_chime(BEEP_VOLUME * 0.5)


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
        _play_mac(_WAV_START)

    def beep_stop():
        pass

    def beep_done():
        _play_mac(_WAV_DONE)

else:
    import sounddevice as sd

    def _play_async(data: np.ndarray):
        try:
            sd.play(data, samplerate=SAMPLE_RATE, blocking=False)
        except Exception as e:
            log.warning(f"Beep failed: {e}")

    def beep_start():
        _play_async(_TONE_START)

    def beep_stop():
        pass

    def beep_done():
        _play_async(_TONE_DONE)
