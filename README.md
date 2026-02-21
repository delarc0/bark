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

---

## Mac Setup

### Requirements

- macOS 13+ (Ventura or later)
- Apple Silicon (M1/M2/M3/M4)
- Python 3.11+ from Homebrew (`brew install python`) -- do NOT use the system `/usr/bin/python3` (too old)
- ffmpeg (`brew install ffmpeg`)
- Homebrew ([brew.sh](https://brew.sh) if you don't have it)

### Step 1: Install system dependencies

Open Terminal and run:

```bash
brew install python ffmpeg
```

### Step 2: Clone and set up

```bash
git clone https://github.com/delarc0/bark.git
cd bark

# IMPORTANT: Use Homebrew Python, not system Python
/opt/homebrew/bin/python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-mac.txt
```

This installs mlx-whisper (Metal-accelerated), Silero VAD, pynput, sounddevice, and other dependencies.

### Step 3: Create the app

```bash
chmod +x create-app.sh
./create-app.sh
```

This creates `Bark.app` in the project folder. You can drag it to your Dock or Applications folder.

### Step 4: First launch

Double-click **Bark.app** in Finder. On first launch:

1. macOS will ask for **Microphone** permission -- click Allow
2. macOS will ask for **Accessibility** permission -- click "Open System Settings", then toggle Bark on under Privacy & Security > Accessibility
3. Bark downloads the Whisper model (~1.5 GB) and Silero VAD model automatically. This takes a minute the first time, then it's cached.

If the overlay doesn't appear after granting permissions, quit and relaunch Bark.app.

### Step 5: Use it

1. A small green overlay appears at the bottom center of your screen
2. **Hold Right Option** (the Option key on the right side of your keyboard) to record
3. Speak -- the overlay shows a waveform animation
4. **Release** to transcribe, or just stop talking (auto-stop after 1.5s of silence)
5. Transcribed text is pasted at your cursor position
6. **Right-click** the overlay to quit

### Mac troubleshooting

| Problem | Fix |
|---------|-----|
| Nothing happens when I press Right Option | Grant Accessibility permission: System Settings > Privacy & Security > Accessibility. Toggle Bark (or Terminal/iTerm if running from terminal) on. Restart Bark. |
| "Bark.app is damaged" or can't be opened | Run `xattr -cr Bark.app` in terminal from the bark folder, then try again. |
| Overlay doesn't appear | Check `dictation.log` in the bark folder for errors. Make sure `.venv` exists. |
| Transcription is slow on first use | The first transcription loads the model into Metal memory. Subsequent ones are ~0.5s. |
| No sound feedback | Check that your default audio output device is set correctly in System Settings > Sound. |
| Model download fails | Make sure you have internet access. The Whisper model downloads from Hugging Face (~1.5 GB). |
| `incompatible architecture` or numpy import error | You're using the system Python (x86_64). Delete `.venv`, then recreate with Homebrew Python: `/opt/homebrew/bin/python3 -m venv .venv` |
| App flashes and closes | Check `dictation.log` for errors. Most common: wrong Python version (need 3.11+ from Homebrew). |

### Updating

```bash
cd bark
git pull
source .venv/bin/activate
pip install -r requirements-mac.txt
./create-app.sh
```

---

## Windows Setup

### Requirements

- Windows 10/11
- NVIDIA GPU with CUDA support (tested on RTX 4090)
- Python 3.11+
- NVIDIA drivers (CUDA 12.x)

### Setup

```bash
git clone https://github.com/delarc0/bark.git
cd bark

python -m venv .venv
.venv\Scripts\activate

# PyTorch with CUDA (required for Silero VAD)
pip install torch --index-url https://download.pytorch.org/whl/cu121

pip install -r requirements.txt
```

### Usage

```bash
.venv\Scripts\python dictation.py    # With console
.venv\Scripts\pythonw dictation.py   # Without console
start.bat                            # Double-click launcher
```

1. A small green overlay appears at the bottom center of your screen
2. **Hold Caps Lock** to record (Caps Lock is suppressed, won't toggle)
3. Speak -- the overlay shows a waveform animation
4. **Release** to transcribe, or just stop talking (auto-stop after 1.5s of silence)
5. Transcribed text is pasted at your cursor position
6. **Right-click** the overlay to quit

### Updating

```bash
cd bark
git pull
.venv\Scripts\activate
pip install -r requirements.txt
```

---

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
