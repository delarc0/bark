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

### Install

```bash
git clone https://github.com/delarc0/bark.git
cd bark
chmod +x setup-mac.sh
./setup-mac.sh
```

The setup script handles everything automatically: Homebrew, Python, dependencies, and building Bark.app.

### First launch

Double-click **Bark.app** (or drag it to your Dock). On first launch:

1. Grant **Microphone** permission when prompted
2. Grant **Accessibility** permission (System Settings > Privacy & Security > Accessibility > toggle Bark on)
3. The Whisper model downloads automatically (~1.5 GB, cached after first time)

If the overlay doesn't appear after granting permissions, quit and relaunch.

### Usage

1. A small green overlay appears at the bottom center of your screen
2. **Hold Right Option** (the Option key on the right side) to record
3. Speak -- the overlay shows a waveform animation
4. **Release** to transcribe, or just stop talking (auto-stop after 1.5s of silence)
5. Transcribed text is pasted at your cursor position
6. **Right-click** the overlay to quit

### Updating

```bash
cd bark
git pull
./setup-mac.sh
```

### Troubleshooting

| Problem | Fix |
|---------|-----|
| Nothing happens when I press Right Option | Grant Accessibility permission: System Settings > Privacy & Security > Accessibility. Toggle Bark on. Restart Bark. |
| "Bark.app is damaged" | Run `xattr -cr Bark.app` in Terminal, then try again. |
| Overlay doesn't appear | Check `dictation.log` for errors. Run `./setup-mac.sh` to rebuild. |
| Transcription is slow first time | Normal -- model loads into Metal memory once. Subsequent runs are ~0.5s. |

<details>
<summary>Manual setup (advanced)</summary>

If you prefer to set things up manually:

```bash
brew install python ffmpeg
/opt/homebrew/bin/python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-mac.txt
chmod +x create-app.sh
./create-app.sh
```

Important: use `/opt/homebrew/bin/python3`, not the system `/usr/bin/python3` (too old, wrong architecture).

</details>

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

Built by [LAB37](https://lab37.io)
