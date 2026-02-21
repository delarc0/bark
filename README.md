# Bark

**GPU-powered local dictation tool by LAB37.**

Hold a key, speak, release. Text appears wherever your cursor is. No cloud, no API keys, no subscription. Runs entirely on your machine.

## Features

- **Hold-to-dictate** - Push-to-talk trigger (Caps Lock on Windows, Right Option on Mac)
- **Auto-stop** - Stops recording automatically when you stop speaking (Silero VAD)
- **Pre-buffer** - Captures audio before you press the key so first words aren't cut off
- **Multi-language** - Auto-detects Swedish, English, and 90+ other languages
- **Fast** - ~0.2s on RTX 4090 (CUDA), ~0.5s on Apple Silicon (MLX Metal)
- **Clean output** - Strips filler words, detects Whisper hallucinations
- **Visual overlay** - Floating status bar with live waveform during recording
- **Audio feedback** - Subtle terminal-style blips on start/done
- **Clipboard paste** - Works in any app (restores clipboard after)
- **Cross-platform** - Windows and macOS

## Requirements

### Windows
- Windows 10/11
- NVIDIA GPU with CUDA support (tested on RTX 4090)
- Python 3.11+
- NVIDIA drivers (CUDA 12.x)

### Mac
- macOS 13+ (Ventura or later)
- Apple Silicon (M1/M2/M3/M4)
- Python 3.11+
- ffmpeg (`brew install ffmpeg`)

## Setup

### Windows

```bash
git clone https://github.com/delarc0/bark.git
cd bark

python -m venv .venv
.venv\Scripts\activate

# PyTorch with CUDA (required for Silero VAD)
pip install torch --index-url https://download.pytorch.org/whl/cu121

pip install -r requirements.txt
```

### Mac

```bash
git clone https://github.com/delarc0/bark.git
cd bark

brew install ffmpeg

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements-mac.txt
```

**Important:** On first launch, macOS will ask for **Accessibility** permission (for keyboard monitoring) and **Microphone** permission. Grant both in System Settings > Privacy & Security.

On first run, Bark will download the Whisper model (~1.5 GB) and Silero VAD model automatically.

## Usage

### Windows

```bash
.venv\Scripts\python dictation.py    # With console
.venv\Scripts\pythonw dictation.py   # Without console
start.bat                            # Double-click launcher
```

### Mac

```bash
python dictation.py
# or
./start.sh
```

1. A small overlay appears at the bottom center of your screen
2. **Hold Caps Lock** (Windows) or **Right Option** (Mac) to record
3. Speak -- overlay shows waveform animation
4. **Release** to transcribe (or wait for auto-stop after silence)
5. Text is pasted at your cursor position
6. **Right-click** the overlay to quit

## Configuration

Edit `config.py` to customize:

| Setting | Default | Description |
|---------|---------|-------------|
| `MODEL_SIZE` | Auto-detected | Whisper model (platform-specific) |
| `LANGUAGE` | `None` (auto) | Force a specific language, e.g. `"en"` or `"sv"` |
| `AUTO_STOP` | `True` | Auto-stop recording after silence |
| `SILENCE_TIMEOUT` | `1.5` | Seconds of silence before auto-stop |
| `PRE_BUFFER` | `0.5` | Seconds of audio kept before recording starts |
| `BEEP_VOLUME` | `0.3` | Sound effect volume (0.0 - 1.0) |
| `PASTE_DELAY` | `0.15` | Clipboard paste delay in seconds |

## Architecture

```
dictation.py      Main entry point, orchestrates everything
audio.py          Always-on mic stream, pre-buffer, Silero VAD
transcriber.py    Whisper transcription (faster-whisper on Windows, mlx-whisper on Mac)
keyboard_hook.py  Trigger key hook (pynput), clipboard paste
overlay.py        Tkinter floating overlay with waveform visualization
feedback.py       Audio feedback via sounddevice
config.py         Platform detection + configurable settings
```

## Built with

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) - CTranslate2 Whisper (Windows/CUDA)
- [mlx-whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper) - MLX Whisper (Mac/Metal)
- [Silero VAD](https://github.com/snakers4/silero-vad) - Voice activity detection
- [pynput](https://github.com/moses-palmer/pynput) - Keyboard hooks

---

Built by [LAB37](https://lab37.se)
