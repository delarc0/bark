import logging
import re
import numpy as np
from config import MODEL_SIZE, DEVICE, COMPUTE_TYPE, LANGUAGE, BEAM_SIZE, SAMPLE_RATE, IS_MAC

log = logging.getLogger(__name__)

# Filler words to strip (Swedish + English)
# Using (?<!\w) and (?!\w) instead of \b to handle Swedish characters properly
FILLER_WORDS = re.compile(
    r"(?<!\w)(um|uh|uhm|hmm|ah|eh|oh|you know|"
    r"liksom|typ|asså|alltså|öh|äh)(?!\w)",
    re.IGNORECASE,
)

# Whisper hallucination patterns (common on silence/noise)
HALLUCINATIONS = {
    "thank you",
    "thanks for watching",
    "subscribe",
    "tack för att ni tittade",
    "tack för att du tittade",
    "undertextning",
}


def clean_text(text: str) -> str:
    text = text.strip()
    if not text:
        return ""

    # Check for hallucination patterns (exact match only)
    lower = text.lower().strip(".")
    if lower in HALLUCINATIONS:
        return ""

    # Remove filler words
    text = FILLER_WORDS.sub("", text)

    # Collapse multiple spaces
    text = re.sub(r"  +", " ", text).strip()

    # Add trailing space so next dictation doesn't merge with previous
    if text and not text.endswith((" ", "\n")):
        text += " "

    return text


class Transcriber:
    def __init__(self):
        if IS_MAC:
            import mlx_whisper
            self._mlx = mlx_whisper
            log.info(f"Loading model '{MODEL_SIZE}' with MLX (Metal)...")
            # Warm up: run a 1-second silence transcription to load model into memory
            self._mlx.transcribe(
                np.zeros(SAMPLE_RATE, dtype=np.float32),
                path_or_hf_repo=MODEL_SIZE,
            )
            self.model = None
        else:
            from faster_whisper import WhisperModel
            self._mlx = None
            log.info(f"Loading model '{MODEL_SIZE}' on {DEVICE} ({COMPUTE_TYPE})...")
            self.model = WhisperModel(
                MODEL_SIZE,
                device=DEVICE,
                compute_type=COMPUTE_TYPE,
            )
        log.info("Model loaded.")

    def transcribe(self, audio: np.ndarray) -> str:
        if len(audio) == 0:
            return ""

        try:
            if IS_MAC:
                return self._transcribe_mlx(audio)
            else:
                return self._transcribe_faster_whisper(audio)
        except Exception as e:
            log.error(f"Transcription failed: {e}")
            return ""

    def _transcribe_mlx(self, audio: np.ndarray) -> str:
        result = self._mlx.transcribe(
            audio,
            path_or_hf_repo=MODEL_SIZE,
            language=LANGUAGE,
        )

        if LANGUAGE is None and result.get("language"):
            log.info(f"Detected language: {result['language']}")

        text_parts = []
        for segment in result.get("segments", []):
            text_parts.append(segment["text"].strip())

        raw = " ".join(text_parts).strip()
        return clean_text(raw)

    def _transcribe_faster_whisper(self, audio: np.ndarray) -> str:
        segments, info = self.model.transcribe(
            audio,
            beam_size=BEAM_SIZE,
            language=LANGUAGE,
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=500,
                speech_pad_ms=200,
            ),
        )

        if LANGUAGE is None and info:
            log.info(f"Detected language: {info.language} ({info.language_probability:.0%})")

        text_parts = []
        for segment in segments:
            text_parts.append(segment.text.strip())

        raw = " ".join(text_parts).strip()
        return clean_text(raw)
