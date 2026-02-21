# Bark

**GPU-powered local dictation tool by LAB37.**

Hold Caps Lock, speak, release. Text appears wherever your cursor is. No cloud, no API keys, no subscription. Runs entirely on your machine using your NVIDIA GPU.

## Features

- **Hold-to-dictate** - Caps Lock as push-to-talk (suppressed so it doesn't toggle)
- **Auto-stop** - Stops recording automatically when you stop speaking (Silero VAD)
- **Pre-buffer** - Captures audio before you press the key so first words aren't cut off
- **Multi-language** - Auto-detects Swedish, English, and 90+ other languages
- **Fast** - Transcription in ~0.2-0.5s on an RTX 4090 (faster-whisper + CTranslate2)
- **Clean output** - Strips filler words, detects Whisper hallucinations
- **Visual overlay** - Floating status bar with live waveform during recording
- **Audio feedback** - Subtle terminal-style blips on start/done
- **Clipboard paste** - Works in any app (pastes via Ctrl+V, restores clipboard after)

## Requirements

- Windows 10/11
- NVIDIA GPU with CUDA support (tested on RTX 4090)
- Python 3.11+
- NVIDIA drivers (CUDA 12.x)

## Setup

```bash
# Clone
git clone https://github.com/delarc0/bark.git
cd bark

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install PyTorch with CUDA (required for Silero VAD)
pip install torch --index-url https://download.pytorch.org/whl/cu121

# Install dependencies
pip install -r requirements.txt
```

On first run, Bark will download the Whisper model (~1.5 GB) and Silero VAD model automatically.

## Usage

```bash
# Run with console (for debugging)
.venv\Scripts\python dictation.py

# Run without console window
.venv\Scripts\pythonw dictation.py

# Or use the batch launcher
start.bat
```

1. A small overlay appears at the bottom center of your screen
2. **Hold Caps Lock** to record (overlay turns red, waveform animates)
3. **Release** to transcribe (overlay turns yellow while processing)
4. Text is pasted at your cursor position
5. **Right-click** the overlay to quit

## Configuration

Edit `config.py` to customize:

| Setting | Default | Description |
|---------|---------|-------------|
| `MODEL_SIZE` | `deepdml/faster-whisper-large-v3-turbo-ct2` | Whisper model (smaller = faster, less accurate) |
| `LANGUAGE` | `None` (auto) | Force a specific language, e.g. `"en"` or `"sv"` |
| `AUTO_STOP` | `True` | Auto-stop recording after silence |
| `SILENCE_TIMEOUT` | `1.5` | Seconds of silence before auto-stop |
| `PRE_BUFFER` | `0.5` | Seconds of audio kept before recording starts |
| `BEEP_VOLUME` | `0.3` | Sound effect volume (0.0 - 1.0) |
| `PASTE_DELAY` | `0.15` | Clipboard paste delay in seconds |

## Architecture

```
dictation.py    Main entry point, orchestrates everything
audio.py        Always-on mic stream, pre-buffer, Silero VAD
transcriber.py  faster-whisper transcription + text cleanup
keyboard_hook.py  Caps Lock hook (pynput + win32), clipboard paste
overlay.py      Tkinter floating overlay with waveform visualization
feedback.py     Audio feedback (frequency sweep blips)
config.py       All configurable settings
```

## Built with

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) - CTranslate2 Whisper implementation
- [Silero VAD](https://github.com/snakers4/silero-vad) - Voice activity detection
- [pynput](https://github.com/moses-palmer/pynput) - Keyboard hooks

---

Built by [LAB37](https://lab37.se)
