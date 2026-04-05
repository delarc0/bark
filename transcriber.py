import logging
import os
import re
import numpy as np
from config import cfg, MODEL_SIZE, DEVICE, COMPUTE_TYPE, SAMPLE_RATE, IS_MAC
from paths import get_data_dir

log = logging.getLogger(__name__)

CUSTOM_WORDS_PATH = os.path.join(get_data_dir(), "custom_words.txt")

# Cached prompt -- reloaded when file mtime changes
_prompt_cache: str | None = None
_prompt_mtime: float = 0.0


def _load_initial_prompt() -> str | None:
    """Load custom vocabulary from custom_words.txt and format as initial_prompt."""
    global _prompt_cache, _prompt_mtime
    try:
        mtime = os.path.getmtime(CUSTOM_WORDS_PATH)
    except OSError:
        return None
    if mtime == _prompt_mtime:
        return _prompt_cache
    try:
        with open(CUSTOM_WORDS_PATH, "r", encoding="utf-8") as f:
            words = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        _prompt_mtime = mtime
        _prompt_cache = ("Context words: " + ", ".join(words)) if words else None
        return _prompt_cache
    except Exception:
        return None

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

# Self-correction triggers: user wants to replace preceding text
CORRECTION_TRIGGERS = re.compile(
    r"(?<!\w)(no wait|correction|actually no|scratch that|"
    r"let me rephrase|I mean|nej vänta|jag menar|rättelse)(?!\w)",
    re.IGNORECASE,
)


def _apply_corrections(text: str) -> str:
    """If the user self-corrected, keep only text after the last trigger."""
    parts = CORRECTION_TRIGGERS.split(text)
    if len(parts) <= 1:
        return text
    # Take the last segment (after the final correction trigger)
    corrected = parts[-1].strip()
    return corrected if corrected else text


def _fix_punctuation(text: str) -> str:
    """Fix common Whisper punctuation artifacts."""
    # Collapse repeated punctuation (.. → ., !! → !, ?? → ?)
    text = re.sub(r"([.!?])\1+", r"\1", text)
    # Remove space before punctuation
    text = re.sub(r"\s+([.!?,;:])", r"\1", text)
    # Capitalize after sentence-ending punctuation
    text = re.sub(r"([.!?])\s+([a-z])", lambda m: m.group(1) + " " + m.group(2).upper(), text)
    # Remove repeated adjacent words (case-insensitive)
    text = re.sub(r"\b(\w+)\s+\1\b", r"\1", text, flags=re.IGNORECASE)
    return text


def clean_text(text: str) -> str:
    text = text.strip()
    if not text:
        return ""

    # Check for hallucination patterns (exact match only)
    lower = text.lower().strip(".")
    if lower in HALLUCINATIONS:
        return ""

    # Apply self-corrections (before filler removal so triggers are intact)
    text = _apply_corrections(text)

    # Remove filler words
    text = FILLER_WORDS.sub("", text)

    # Collapse multiple spaces and fix punctuation
    text = re.sub(r"  +", " ", text).strip()
    text = _fix_punctuation(text)

    # Add trailing space so next dictation doesn't merge with previous
    if text and not text.endswith((" ", "\n")):
        text += " "

    return text


def _ensure_model_cached(on_progress=None):
    """Pre-download the model with progress reporting if not already cached."""
    if IS_MAC:
        return  # mlx-whisper handles its own downloads

    try:
        from faster_whisper.utils import download_model
        download_model(MODEL_SIZE, local_files_only=True)
        log.info("Model already cached.")
        return
    except Exception:
        pass  # Not cached, need to download

    if not on_progress:
        return  # No callback, let WhisperModel handle it

    log.info(f"Downloading model '{MODEL_SIZE}' from HuggingFace...")

    try:
        import huggingface_hub
        from tqdm.auto import tqdm as _base_tqdm

        class _ProgressTqdm(_base_tqdm):
            def update(self, n=1):
                super().update(n)
                if self.total and self.total > 0:
                    pct = int(self.n / self.total * 100)
                    on_progress(f"DOWNLOADING {pct}%")

        huggingface_hub.snapshot_download(
            MODEL_SIZE,
            tqdm_class=_ProgressTqdm,
        )
        on_progress("LOADING MODEL")
    except Exception as e:
        log.warning(f"Pre-download failed: {e}. WhisperModel will retry.")


class Transcriber:
    def __init__(self, on_progress=None):
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

            _ensure_model_cached(on_progress=on_progress)

            log.info(f"Loading model '{MODEL_SIZE}' on {DEVICE} ({COMPUTE_TYPE})...")
            try:
                self.model = WhisperModel(
                    MODEL_SIZE,
                    device=DEVICE,
                    compute_type=COMPUTE_TYPE,
                )
            except Exception as e:
                if DEVICE == "cuda":
                    log.warning(f"CUDA init failed: {e} - falling back to CPU")
                    self.model = WhisperModel(
                        MODEL_SIZE,
                        device="cpu",
                        compute_type="int8",
                    )
                else:
                    raise
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
        kwargs = dict(
            path_or_hf_repo=MODEL_SIZE,
            language=cfg["language"],
        )
        prompt = _load_initial_prompt()
        if prompt:
            kwargs["initial_prompt"] = prompt
        result = self._mlx.transcribe(audio, **kwargs)

        if cfg["language"] is None and result.get("language"):
            log.info(f"Detected language: {result['language']}")

        raw = " ".join(s["text"].strip() for s in result.get("segments", [])).strip()
        return clean_text(raw)

    def transcribe_preview(self, audio: np.ndarray) -> str:
        """Fast preview transcription (lower quality, for streaming display)."""
        if len(audio) == 0:
            return ""
        try:
            prompt = _load_initial_prompt()
            if IS_MAC:
                kwargs = dict(
                    path_or_hf_repo=MODEL_SIZE,
                    language=cfg["language"],
                )
                if prompt:
                    kwargs["initial_prompt"] = prompt
                result = self._mlx.transcribe(audio, **kwargs)
                raw = " ".join(s["text"].strip() for s in result.get("segments", [])).strip()
            else:
                segments, _ = self.model.transcribe(
                    audio,
                    beam_size=1,
                    language=cfg["language"],
                    initial_prompt=prompt,
                    vad_filter=False,
                )
                raw = " ".join(s.text.strip() for s in segments).strip()
            return clean_text(raw)
        except Exception as e:
            log.debug(f"Preview transcription failed: {e}")
            return ""

    def _transcribe_faster_whisper(self, audio: np.ndarray) -> str:
        segments, info = self.model.transcribe(
            audio,
            beam_size=cfg["beam_size"],
            language=cfg["language"],
            initial_prompt=_load_initial_prompt(),
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=500,
                speech_pad_ms=200,
            ),
        )

        if cfg["language"] is None and info:
            log.info(f"Detected language: {info.language} ({info.language_probability:.0%})")

        raw = " ".join(s.text.strip() for s in segments).strip()
        return clean_text(raw)
