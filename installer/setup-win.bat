@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo   ==============================
echo     Bark - Windows Setup
echo   ==============================
echo.

:: ── Step 1: Check NVIDIA GPU ──────────────────────────────────────
echo [1/5] Checking NVIDIA GPU...
set GPU_OK=0
for /f "tokens=*" %%g in ('nvidia-smi --query-gpu=name --format^=csv^,noheader 2^>nul') do (
    echo   Found: %%g
    set GPU_OK=1
)
if "!GPU_OK!"=="0" (
    echo.
    echo   ERROR: NVIDIA GPU not detected.
    echo   Bark requires an NVIDIA GPU with CUDA support.
    echo   Make sure NVIDIA drivers are installed:
    echo   https://www.nvidia.com/drivers
    echo.
    pause
    exit /b 1
)
echo.

:: ── Step 2: Check/Install Python ──────────────────────────────────
echo [2/5] Checking Python 3.11+...

set PYTHON=
set PYVER=
set PY_MAJOR=0
set PY_MINOR=0

:: Check if python is available
where python >nul 2>&1
if errorlevel 1 goto :install_python

:: Get version string
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
for /f "tokens=1,2 delims=." %%a in ("!PYVER!") do (
    set PY_MAJOR=%%a
    set PY_MINOR=%%b
)

if !PY_MAJOR! NEQ 3 goto :install_python
if !PY_MINOR! LSS 11 goto :install_python

set PYTHON=python
echo   Found: Python !PYVER!
goto :python_ok

:install_python
echo   Python 3.11+ not found. Installing via winget...
echo.
winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
if errorlevel 1 (
    echo.
    echo   ERROR: Could not install Python automatically.
    echo   Please install Python 3.12+ manually from:
    echo   https://www.python.org/downloads/
    echo   Make sure to check "Add Python to PATH" during install.
    echo   Then re-run this script.
    echo.
    pause
    exit /b 1
)

:: Add likely install paths to current session PATH
set "PATH=%LOCALAPPDATA%\Programs\Python\Python312\;%LOCALAPPDATA%\Programs\Python\Python312\Scripts\;!PATH!"

where python >nul 2>&1
if errorlevel 1 (
    echo.
    echo   Python was installed but is not in PATH yet.
    echo   Please close this window and re-run setup-win.bat
    echo   (or restart your computer).
    echo.
    pause
    exit /b 1
)
set PYTHON=python
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do echo   Installed: Python %%v

:python_ok
echo.

:: ── Step 3: Create virtual environment ────────────────────────────
echo [3/5] Creating virtual environment...
if exist ".venv" (
    echo   Removing existing venv...
    rmdir /s /q ".venv"
)
!PYTHON! -m venv .venv
if errorlevel 1 (
    echo.
    echo   ERROR: Failed to create virtual environment.
    echo.
    pause
    exit /b 1
)
echo   venv created.
echo.

:: ── Step 4: Install PyTorch with CUDA ─────────────────────────────
echo [4/5] Installing PyTorch with CUDA support...
echo   (This may take several minutes)
echo.
.venv\Scripts\pip.exe install --upgrade pip --quiet
.venv\Scripts\pip.exe install torch --index-url https://download.pytorch.org/whl/cu121
if errorlevel 1 (
    echo.
    echo   ERROR: PyTorch installation failed.
    echo   Check your internet connection and try again.
    echo.
    pause
    exit /b 1
)
echo.

:: ── Step 5: Install remaining dependencies ────────────────────────
echo [5/5] Installing dependencies...
.venv\Scripts\pip.exe install -r requirements.txt
if errorlevel 1 (
    echo.
    echo   ERROR: Dependency installation failed.
    echo.
    pause
    exit /b 1
)
echo.

:: ── Done ──────────────────────────────────────────────────────────
echo   ========================================
echo     Setup complete!
echo.
echo     Launch Bark from:
echo     - Desktop shortcut
echo     - Start Menu ^> Bark
echo.
echo     First launch: the Whisper model
echo     downloads automatically (~1.5 GB).
echo   ========================================
echo.
pause
