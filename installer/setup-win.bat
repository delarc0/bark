@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo   ==============================
echo     Bark - Windows Setup
echo   ==============================
echo.

:: ── Pre-flight checks ───────────────────────────────────────────

:: Check 64-bit Windows
if "%PROCESSOR_ARCHITECTURE%"=="x86" (
    if not defined PROCESSOR_ARCHITEW6432 (
        echo   ERROR: Bark requires 64-bit Windows.
        echo   Your system appears to be 32-bit.
        echo.
        pause
        exit /b 1
    )
)

:: Check disk space (~5 GB needed for venv + model)
for /f "tokens=3" %%a in ('dir /-c "%~dp0" 2^>nul ^| findstr /c:"bytes free"') do set FREE_BYTES=%%a
set FREE_BYTES=!FREE_BYTES:,=!
:: Simple check: if free space string is less than 10 chars, likely under 5GB
if defined FREE_BYTES (
    set "FB=!FREE_BYTES!"
    :: 5 GB = 5368709120 bytes (10 digits). Less than 10 digits = under ~1GB
    set "LEN=0"
    for /l %%i in (0,1,12) do if "!FB:~%%i,1!" neq "" set /a LEN+=1
    if !LEN! LSS 10 (
        echo   WARNING: Low disk space detected.
        echo   Bark needs ~5 GB for Python packages and the AI model.
        echo.
        choice /c YN /m "  Continue anyway?"
        if errorlevel 2 exit /b 1
    )
)

:: Check internet connectivity
echo   Checking internet connection...
ping -n 1 -w 3000 pypi.org >nul 2>&1
if errorlevel 1 (
    ping -n 1 -w 3000 8.8.8.8 >nul 2>&1
    if errorlevel 1 (
        echo.
        echo   ERROR: No internet connection detected.
        echo   Bark needs internet to download Python packages.
        echo   Check your connection and try again.
        echo.
        pause
        exit /b 1
    )
)
echo   OK
echo.

:: ── Step 1: Check NVIDIA GPU ──────────────────────────────────────
echo [1/6] Checking NVIDIA GPU...
set GPU_OK=0
set GPU_NAME=

:: Method 1: Try nvidia-smi (available if NVIDIA drivers installed from nvidia.com)
for /f "tokens=*" %%g in ('nvidia-smi --query-gpu=name --format^=csv^,noheader 2^>nul') do (
    set "GPU_NAME=%%g"
    set GPU_OK=1
)

:: Method 2: Try nvidia-smi from known install paths
if "!GPU_OK!"=="0" (
    for %%p in (
        "C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe"
        "C:\Windows\System32\nvidia-smi.exe"
    ) do (
        if exist %%p (
            for /f "tokens=*" %%g in ('%%p --query-gpu=name --format^=csv^,noheader 2^>nul') do (
                set "GPU_NAME=%%g"
                set GPU_OK=1
            )
        )
    )
)

:: Method 3: Fall back to WMI (works even without nvidia-smi in PATH)
if "!GPU_OK!"=="0" (
    for /f "tokens=*" %%g in ('wmic path win32_VideoController where "name like '%%NVIDIA%%'" get name /value 2^>nul ^| findstr /i "NVIDIA"') do (
        set "GPU_NAME=%%g"
        set GPU_OK=1
    )
)

if "!GPU_OK!"=="1" (
    echo   Found: !GPU_NAME!
    :: Check NVIDIA driver version (CUDA 12.1 needs driver 525+)
    for /f "tokens=*" %%v in ('nvidia-smi --query-gpu=driver_version --format^=csv^,noheader 2^>nul') do (
        echo   Driver: %%v
        for /f "tokens=1 delims=." %%m in ("%%v") do (
            if %%m LSS 525 (
                echo.
                echo   WARNING: Driver version %%v may be too old for CUDA 12.
                echo   Update from: https://www.nvidia.com/drivers
                echo   Falling back to CPU mode for now.
                set GPU_OK=0
            )
        )
    )
) else (
    echo.
    echo   WARNING: NVIDIA GPU not detected.
    echo   Bark works best with an NVIDIA GPU ^(CUDA^), but will
    echo   fall back to CPU mode if needed ^(slower transcription^).
    echo.
    echo   If you DO have an NVIDIA GPU, install drivers from:
    echo   https://www.nvidia.com/drivers
    echo.
    choice /c YN /m "  Continue with CPU-only setup?"
    if errorlevel 2 exit /b 1
)
echo.

:: ── Step 2: Check/Install Python ──────────────────────────────────
echo [2/6] Checking Python 3.11+...

set PYTHON=
set PYVER=
set PY_MAJOR=0
set PY_MINOR=0

:: Check if python is available
where python >nul 2>&1
if errorlevel 1 goto :install_python

:: Make sure it's real Python, not the Windows Store stub
python -c "import sys; sys.exit(0)" >nul 2>&1
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

:: ── Step 3: Check Visual C++ Runtime ────────────────────────────
echo [3/6] Checking Visual C++ Runtime...
set VCRT_OK=0
reg query "HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\X64" /v Version >nul 2>&1
if not errorlevel 1 set VCRT_OK=1
if "!VCRT_OK!"=="0" (
    reg query "HKLM\SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\X64" /v Version >nul 2>&1
    if not errorlevel 1 set VCRT_OK=1
)
if "!VCRT_OK!"=="1" (
    echo   OK
) else (
    echo   Visual C++ Runtime not found. Installing...
    winget install Microsoft.VCRedist.2015+.x64 --accept-package-agreements --accept-source-agreements >nul 2>&1
    if errorlevel 1 (
        echo.
        echo   WARNING: Could not install Visual C++ Runtime automatically.
        echo   If Bark crashes on launch, install it manually from:
        echo   https://aka.ms/vs/17/release/vc_redist.x64.exe
    ) else (
        echo   Installed.
    )
)
echo.

:: ── Step 4: Create virtual environment ──────────────────────────
echo [4/6] Checking virtual environment...
set VENV_OK=0
if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe -c "import sys; sys.exit(0)" >nul 2>&1
    if not errorlevel 1 set VENV_OK=1
)
if "!VENV_OK!"=="1" (
    echo   Existing venv OK - reusing.
) else (
    echo   Creating virtual environment...
    if exist ".venv" (
        echo   Removing broken venv...
        rmdir /s /q ".venv"
    )
    !PYTHON! -m venv .venv
    if errorlevel 1 (
        echo.
        echo   ERROR: Failed to create virtual environment.
        echo   Try running this script as Administrator, or check
        echo   that your antivirus isn't blocking Python.
        echo.
        pause
        exit /b 1
    )
    echo   venv created.
)
echo.

:: ── Step 5: Install PyTorch ─────────────────────────────────────
.venv\Scripts\pip.exe install --upgrade pip --quiet 2>nul
if "!GPU_OK!"=="1" (
    echo [5/6] Installing PyTorch with CUDA support...
    echo   (This may take several minutes - ~2.5 GB download)
    echo.
    .venv\Scripts\pip.exe install torch --index-url https://download.pytorch.org/whl/cu121
    if errorlevel 1 (
        echo.
        echo   CUDA PyTorch failed. Trying CPU-only version...
        echo.
        .venv\Scripts\pip.exe install torch --index-url https://download.pytorch.org/whl/cpu
    )
) else (
    echo [5/6] Installing PyTorch ^(CPU-only^)...
    echo   (This may take a few minutes)
    echo.
    .venv\Scripts\pip.exe install torch --index-url https://download.pytorch.org/whl/cpu
)
if errorlevel 1 (
    echo.
    echo   ERROR: PyTorch installation failed.
    echo   - Check your internet connection
    echo   - Make sure antivirus isn't blocking downloads
    echo   - Try running this script again
    echo.
    pause
    exit /b 1
)
echo.

:: ── Step 6: Install remaining dependencies ──────────────────────
echo [6/6] Installing dependencies...
.venv\Scripts\pip.exe install -r requirements.txt
if errorlevel 1 (
    echo.
    echo   ERROR: Dependency installation failed.
    echo   - Check your internet connection
    echo   - Try running this script again
    echo.
    pause
    exit /b 1
)
if "!GPU_OK!"=="1" (
    .venv\Scripts\pip.exe install nvidia-cublas-cu12 nvidia-cudnn-cu12 --quiet
)
echo.

:: ── Verify installation ─────────────────────────────────────────
echo   Verifying installation...
.venv\Scripts\python.exe -c "import faster_whisper; import sounddevice; import pynput; print('OK')" 2>nul
if errorlevel 1 (
    echo.
    echo   WARNING: Some packages may not have installed correctly.
    echo   Bark might still work - try launching it.
    echo   If it crashes, check dictation.log for details.
    echo.
) else (
    echo   All dependencies verified.
)
echo.

:: ── Write version marker (used by start.bat to detect updates) ──
if exist "VERSION" (
    copy /y VERSION .setup-version >nul
) else (
    echo unknown> .setup-version
)

:: ── Done ────────────────────────────────────────────────────────
if "!GPU_OK!"=="1" (
    echo   ========================================
    echo     Setup complete! ^(GPU: !GPU_NAME!^)
) else (
    echo   ========================================
    echo     Setup complete! ^(CPU mode^)
)
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
