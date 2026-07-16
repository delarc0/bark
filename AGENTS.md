# AGENTS.md: installing Bark on Windows

Instructions for a coding agent (Claude Code, etc.) asked to install Bark on
this Windows PC. Follow them top to bottom. Bark is a local dictation app:
hold a hotkey, speak, release, and the transcribed text is pasted at the
cursor. Everything runs on-device (faster-whisper); no account, no cloud, no
API keys.

On a Mac? Use the native Mac app instead: https://github.com/delarc0/bark-mac
(it has its own AGENTS.md).

## TL;DR

Download the latest installer from GitHub releases and run it. No admin
rights needed; it installs per-user to `%LOCALAPPDATA%\Bark`.

```powershell
$asset = (Invoke-RestMethod https://api.github.com/repos/delarc0/bark/releases/latest).assets |
  Where-Object name -like "*-Setup.exe" | Select-Object -First 1
curl.exe -L -o "$env:TEMP\Bark-Setup.exe" $asset.browser_download_url
Unblock-File "$env:TEMP\Bark-Setup.exe" -ErrorAction SilentlyContinue
Start-Process "$env:TEMP\Bark-Setup.exe" -ArgumentList "/SILENT" -Wait
Start-Process "$env:LOCALAPPDATA\Bark\Bark.exe"
```

Notes:

- The installer is large (~650 MB): it bundles Python, PyTorch/CUDA and all
  dependencies, so nothing else needs to be installed. The download is the
  slow part; tell the user.
- Use `curl.exe` (bundled with Windows 10/11) for the download, not
  `Invoke-WebRequest`: it is much faster on large files and does not tag the
  file with Mark-of-the-Web. `Unblock-File` stays as a belt-and-suspenders
  step so SmartScreen never blocks the unsigned installer. If the user runs
  the installer by double-clicking a browser-downloaded copy instead, they
  will see "Unknown Publisher": click **More info**, then **Run anyway**.
  That is expected; the installer is not code-signed yet.
- `/SILENT` shows only a progress bar. Use `/VERYSILENT` for fully headless.
  Drop the flag entirely if the user wants the normal install wizard (it also
  offers a desktop shortcut).
- The installer does not auto-launch the app, hence the final `Start-Process`.

## Requirements

- Windows 10 or 11, x64
- NVIDIA GPU with CUDA drivers (recommended, transcription in ~0.2s) or
  CPU-only mode (works, slower)
- A working microphone

## First launch

1. The Whisper model downloads automatically (~1.5 GB, one time). The first
   transcription waits for it; later ones are fast. Tell the user to expect
   this.
2. A small pill overlay appears near the bottom of the screen and a Bark icon
   appears in the system tray (notification area).
3. **Hold Caps Lock**, speak, release. Text is pasted at the cursor. A quick
   tap still toggles Caps Lock normally; only holding it records.
4. Settings (language, trigger key, dark mode, auto-stop) are in the
   right-click menu of the tray icon or the overlay.

## Verify the install

Open Notepad, hold Caps Lock, say "testing, one two three", release. The text
should appear within a second or two. If nothing happens, check the log at
`%LOCALAPPDATA%\Bark\dictation.log`.

## Updating

Same procedure: download the latest Setup.exe and run it. Settings
(`bark_config.json`) and history (`bark_history.txt`) in `%LOCALAPPDATA%\Bark`
are preserved.

## Uninstall

Windows Settings > Apps > Bark, or run the uninstaller in
`%LOCALAPPDATA%\Bark`.

## Install from source (developers only)

```
git clone https://github.com/delarc0/bark.git
cd bark
installer\setup-win.bat
```

Requires Python 3.11-3.13 and NVIDIA drivers with CUDA 12.x for GPU mode. The
script creates a venv, detects the GPU, installs PyTorch (CUDA or CPU) and
launches Bark.
