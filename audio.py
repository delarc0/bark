import logging
import threading
from collections import deque

import numpy as np
import sounddevice as sd
import torch
from config import SAMPLE_RATE, CHANNELS, DTYPE, SILENCE_TIMEOUT, PRE_BUFFER

log = logging.getLogger(__name__)

# Silero VAD expects 512 samples at 16kHz (32ms chunks)
VAD_CHUNK_SAMPLES = 512
SPEECH_MIN_DURATION = 0.3  # Must detect speech before auto-stop kicks in

# Pre-buffer: keep last N chunks. At 16kHz with ~512-sample callbacks,
# 0.5s = ~16 callbacks. Use generous maxlen to handle varying chunk sizes.
_PRE_BUFFER_MAXLEN = max(int(SAMPLE_RATE * PRE_BUFFER / 256) + 5, 20)


class AudioRecorder:
    def __init__(self):
        self._pre_buffer: deque[np.ndarray] = deque(maxlen=_PRE_BUFFER_MAXLEN)
        self._chunks: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._on_silence = None
        self._vad_model = None
        self._vad_buffer = np.zeros(0, dtype=np.float32)
        self._silence_samples = 0
        self._speech_detected = False
        self._speech_samples = 0
        self._stopped = False
        self._recording = False
        self._current_level = 0.0
        self._lock = threading.Lock()
        self._load_vad()
        self._start_stream()

    def _load_vad(self):
        log.info("Loading Silero VAD...")
        self._vad_model, _ = torch.hub.load(
            "snakers4/silero-vad", "silero_vad", trust_repo=True
        )
        self._vad_model.eval()
        log.info("VAD loaded.")

    def _start_stream(self):
        """Start the always-on mic stream for pre-buffering."""
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            callback=self._callback,
        )
        self._stream.start()
        log.info("Mic stream started (pre-buffering).")

    def start(self, on_silence=None):
        with self._lock:
            # Grab pre-buffer as initial recording chunks
            pre_samples = int(PRE_BUFFER * SAMPLE_RATE)
            pre_chunks = list(self._pre_buffer)
            self._pre_buffer.clear()

            # Trim pre-buffer to exactly PRE_BUFFER seconds
            if pre_chunks:
                all_pre = np.concatenate(pre_chunks, axis=0)
                flat = all_pre.flatten()
                if len(flat) > pre_samples:
                    flat = flat[-pre_samples:]
                # Reshape to (N, 1) to match live recording chunks from sounddevice
                self._chunks = [flat.reshape(-1, 1)]
            else:
                self._chunks = []

            self._on_silence = on_silence
            self._vad_buffer = np.zeros(0, dtype=np.float32)
            self._silence_samples = 0
            self._speech_detected = False
            self._speech_samples = 0
            self._stopped = False
            self._recording = True
            self._stopped_audio = None
            self._vad_model.reset_states()

    def stop(self) -> np.ndarray:
        with self._lock:
            if self._stopped:
                self._recording = False
                return self._stopped_audio if self._stopped_audio is not None else np.array([], dtype=np.float32)
            self._stopped = True
            self._recording = False
            if not self._chunks:
                return np.array([], dtype=np.float32)
            audio = np.concatenate(self._chunks, axis=0).flatten()
            self._chunks = []
            return audio

    def shutdown(self):
        """Close the mic stream entirely (call on app exit)."""
        with self._lock:
            self._recording = False
            self._stopped = True
            if self._stream:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception as e:
                    log.warning(f"Stream close error: {e}")
                self._stream = None
        log.info("Mic stream shut down.")

    def _callback(self, indata, frames, time, status):
        if status:
            log.warning(f"Audio device: {status}")

        data = indata.copy()

        if self._recording and not self._stopped:
            # Recording mode - collect chunks
            self._chunks.append(data)
            self._current_level = min(1.0, float(np.sqrt(np.mean(data ** 2))) * 12)
            self._process_vad(data)
        else:
            # Pre-buffer mode - keep rolling buffer
            self._pre_buffer.append(data)
            self._current_level = 0.0

    def get_level(self) -> float:
        """Current audio RMS level (0.0 to 1.0) for visualization."""
        return self._current_level

    def _process_vad(self, data):
        if self._on_silence is None:
            return

        flat = data.flatten()
        self._vad_buffer = np.concatenate([self._vad_buffer, flat])

        while len(self._vad_buffer) >= VAD_CHUNK_SAMPLES:
            chunk = self._vad_buffer[:VAD_CHUNK_SAMPLES]
            self._vad_buffer = self._vad_buffer[VAD_CHUNK_SAMPLES:]

            tensor = torch.from_numpy(chunk)
            try:
                prob = self._vad_model(tensor, SAMPLE_RATE).item()
            except Exception as e:
                log.warning(f"VAD error: {e}")
                continue

            if prob > 0.5:
                self._speech_detected = True
                self._speech_samples += VAD_CHUNK_SAMPLES
                self._silence_samples = 0
            else:
                self._silence_samples += VAD_CHUNK_SAMPLES

            # Auto-stop: speech was detected, then silence for SILENCE_TIMEOUT
            if (
                self._speech_detected
                and self._speech_samples >= SPEECH_MIN_DURATION * SAMPLE_RATE
                and self._silence_samples >= SILENCE_TIMEOUT * SAMPLE_RATE
            ):
                self._stopped = True
                self._recording = False
                if self._chunks:
                    self._stopped_audio = np.concatenate(self._chunks, axis=0).flatten()
                    self._chunks = []
                else:
                    self._stopped_audio = np.array([], dtype=np.float32)
                self._vad_buffer = np.zeros(0, dtype=np.float32)
                threading.Thread(target=self._on_silence, daemon=True).start()
                return
