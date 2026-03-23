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
- **System tray** - Full settings menu from the system tray icon (Windows) or menu bar (Mac)
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
6. **Right-click** the overlay or the **menu bar icon** to access settings or quit

### Updating

```bash
cd bark
git pull
./setup-mac.sh
```

The setup script detects your existing virtual environment and reuses it -- only new/changed packages are installed. Bark.app is rebuilt automatically.

> **Coming from v1.0 or an old version?** If you have problems after updating, do a clean install:
> ```bash
> cd bark
> git pull
> rm -rf .venv Bark.app
> ./setup-mac.sh
> ```
> Your settings (`bark_config.json`) and history (`bark_history.txt`) are preserved.

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
- NVIDIA GPU with CUDA support (recommended) or CPU-only mode

### Install

Download and run **Bark-Setup.exe** from the [latest release](https://github.com/delarc0/bark/releases/latest). No Python or developer tools needed -- everything is bundled.

After install, search **"Bark"** in the Start Menu or use the Desktop shortcut.

> **Note:** Windows SmartScreen may show an "Unknown Publisher" warning. Click "More info" then "Run anyway". This is because the installer is not code-signed (yet).

<details>
<summary>Install from source (developers)</summary>

```bash
git clone https://github.com/delarc0/bark.git
cd bark
installer\setup-win.bat
```

The setup script creates a virtual environment, detects your GPU, installs PyTorch (CUDA or CPU), and launches Bark when done.

Requirements for source install: Python 3.11+, NVIDIA drivers with CUDA 12.x (for GPU mode).

</details>

### First launch

1. The Whisper model downloads automatically (~1.5 GB, one-time download)
2. A small green overlay appears near the bottom of your screen
3. Bark appears in your **system tray** (notification area) with a menu for all settings

### Usage

1. **Hold Caps Lock** to record (Caps Lock is suppressed, won't toggle)
2. Speak -- the overlay shows a waveform animation
3. **Release** to transcribe, or just stop talking (auto-stop after 1.5s of silence)
4. Transcribed text appears at your cursor position
5. **Right-click** the overlay or the **system tray icon** to access settings (language, trigger key, dark mode, etc.)

### Updating

Download the latest installer from [releases](https://github.com/delarc0/bark/releases/latest) and run it again. Your settings and history are preserved.

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
