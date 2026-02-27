@echo off
setlocal EnableDelayedExpansion

:: Navigate to project root (where dictation.py lives)
:: Works whether run from project root (Inno install) or installer/ subdir (git clone)
cd /d "%~dp0"
if not exist "dictation.py" (
    if exist "..\dictation.py" (
        cd /d "%~dp0.."
    ) else (
        echo.
        echo   ERROR: Cannot find Bark project files.
        echo   Run this script from the Bark directory.
        echo.
        pause
        exit /b 1
    )
)

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
:: Use WMIC (locale-independent) instead of parsing dir output
set FREE_GB=999
for /f "skip=1 tokens=1" %%a in ('wmic logicaldisk where "DeviceID='%CD:~0,2%'" get FreeSpace 2^>nul') do (
    if not "%%a"=="" (
        set "FREE_BYTES=%%a"
    )
)
if defined FREE_BYTES (
    :: 5 GB = 5368709120. Check digit count (less than 10 digits = under ~1GB)
    set "FB=!FREE_BYTES!"
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

:: ── Step 1: Detect NVIDIA GPU ───────────────────────────────────
echo [1/7] Detecting NVIDIA GPU...
set GPU_OK=0
set GPU_NAME=
set NVIDIA_SMI=

:: Locate nvidia-smi executable
where nvidia-smi >nul 2>nul && set "NVIDIA_SMI=nvidia-smi"
if not defined NVIDIA_SMI (
    for %%p in (
        "%SystemRoot%\System32\nvidia-smi.exe"
        "%ProgramFiles%\NVIDIA Corporation\NVSMI\nvidia-smi.exe"
        "%ProgramW6432%\NVIDIA Corporation\NVSMI\nvidia-smi.exe"
        "%SystemRoot%\SysWOW64\nvidia-smi.exe"
    ) do (
        if not defined NVIDIA_SMI if exist "%%~p" set "NVIDIA_SMI=%%~p"
    )
)
:: Also check DriverStore (some installs only have nvidia-smi here)
if not defined NVIDIA_SMI (
    for /f "delims=" %%p in ('dir /b /s "%SystemRoot%\System32\DriverStore\FileRepository\nv*\nvidia-smi.exe" 2^>nul') do (
        if not defined NVIDIA_SMI set "NVIDIA_SMI=%%p"
    )
)

:: Method 1a: nvidia-smi --query-gpu (best source - exact GPU name + driver version)
if defined NVIDIA_SMI (
    "!NVIDIA_SMI!" --query-gpu=name --format=csv,noheader > "%TEMP%\bark_gpu.txt" 2>nul
    if exist "%TEMP%\bark_gpu.txt" (
        for /f "usebackq delims=" %%g in ("%TEMP%\bark_gpu.txt") do (
            if not "%%g"=="" (
                set "GPU_NAME=%%g"
                set GPU_OK=1
            )
        )
        del "%TEMP%\bark_gpu.txt" 2>nul
    )
    if "!GPU_OK!"=="1" (
        echo   Found: !GPU_NAME!
        "!NVIDIA_SMI!" --query-gpu=driver_version --format=csv,noheader > "%TEMP%\bark_drv.txt" 2>nul
        if exist "%TEMP%\bark_drv.txt" (
            for /f "usebackq delims=" %%v in ("%TEMP%\bark_drv.txt") do (
                if not "%%v"=="" echo   Driver: %%v
            )
            del "%TEMP%\bark_drv.txt" 2>nul
        )
    )
)

:: Method 1b: nvidia-smi -L (simpler format, works on older drivers)
if "!GPU_OK!"=="0" if defined NVIDIA_SMI (
    echo   --query-gpu failed, trying nvidia-smi -L...
    "!NVIDIA_SMI!" -L > "%TEMP%\bark_gpu.txt" 2>nul
    if exist "%TEMP%\bark_gpu.txt" (
        for /f "usebackq tokens=1,* delims=:" %%a in ("%TEMP%\bark_gpu.txt") do (
            if not "%%b"=="" (
                :: Line looks like "GPU 0: NVIDIA GeForce RTX 3070 (UUID: GPU-xxx)"
                :: Extract name before the UUID parenthetical
                set "_LINE=%%b"
                for /f "tokens=1 delims=(" %%n in ("!_LINE!") do (
                    set "GPU_NAME=%%n"
                    :: Trim leading space
                    if "!GPU_NAME:~0,1!"==" " set "GPU_NAME=!GPU_NAME:~1!"
                    set GPU_OK=1
                )
            )
        )
        del "%TEMP%\bark_gpu.txt" 2>nul
    )
    if "!GPU_OK!"=="1" echo   Found: !GPU_NAME!
)

:: Method 2: WMIC (simple, no execution policy issues)
if "!GPU_OK!"=="0" (
    if defined NVIDIA_SMI (
        echo   nvidia-smi found but could not query GPU.
    ) else (
        echo   nvidia-smi not found.
    )
    echo   Checking via WMIC...
    wmic path win32_VideoController where "name like '%%NVIDIA%%'" get name /value > "%TEMP%\bark_gpu.txt" 2>nul
    if exist "%TEMP%\bark_gpu.txt" (
        for /f "usebackq tokens=2 delims==" %%g in ("%TEMP%\bark_gpu.txt") do (
            if not "%%g"=="" (
                set "GPU_NAME=%%g"
                set GPU_OK=1
            )
        )
        del "%TEMP%\bark_gpu.txt" 2>nul
    )
    if "!GPU_OK!"=="1" (
        echo   Found: !GPU_NAME!
    )
)

:: Method 3: PowerShell Get-CimInstance (reliable fallback, works without nvidia-smi)
:: This queries the Windows device manager directly - works on all Windows 10+
if "!GPU_OK!"=="0" (
    echo   WMIC did not find NVIDIA GPU.
    echo   Checking via PowerShell...
    powershell -NoProfile -Command "Get-CimInstance Win32_VideoController | Where-Object {$_.Name -like '*NVIDIA*'} | Select-Object -First 1 -ExpandProperty Name" > "%TEMP%\bark_gpu.txt" 2>nul
    if exist "%TEMP%\bark_gpu.txt" (
        for /f "usebackq delims=" %%g in ("%TEMP%\bark_gpu.txt") do (
            if not "%%g"=="" (
                set "GPU_NAME=%%g"
                set GPU_OK=1
            )
        )
        del "%TEMP%\bark_gpu.txt" 2>nul
    )
    if "!GPU_OK!"=="1" (
        echo   Found: !GPU_NAME!
        :: Also get driver version
        powershell -NoProfile -Command "Get-CimInstance Win32_VideoController | Where-Object {$_.Name -like '*NVIDIA*'} | Select-Object -First 1 -ExpandProperty DriverVersion" > "%TEMP%\bark_drv.txt" 2>nul
        if exist "%TEMP%\bark_drv.txt" (
            for /f "usebackq delims=" %%v in ("%TEMP%\bark_drv.txt") do (
                if not "%%v"=="" echo   Driver: %%v
            )
            del "%TEMP%\bark_drv.txt" 2>nul
        )
    )
)

:: Report GPU detection result
if "!GPU_OK!"=="1" (
    echo   CUDA acceleration will be enabled.
) else (
    echo.
    echo   No NVIDIA GPU detected.
    echo.
    echo   Bark works best with an NVIDIA GPU ^(CUDA^) but will
    echo   fall back to CPU mode ^(slower transcription^).
    echo.
    echo   If you DO have an NVIDIA GPU:
    echo   1. Install or update drivers from https://www.nvidia.com/drivers
    echo   2. Re-run this setup script afterward
    echo.
    choice /c YN /m "  Continue with CPU-only setup?"
    if errorlevel 2 exit /b 1
)
echo.

:: ── Step 2: Check/Install Python ────────────────────────────────
echo [2/7] Checking Python 3.11+...

set PYTHON=
set PYVER=
set PY_MAJOR=0
set PY_MINOR=0

:: Check if python is available and not the Windows Store stub
where python >nul 2>&1
if errorlevel 1 goto :install_python

:: Make sure it's real Python, not the Windows Store redirect
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
if !PY_MINOR! GEQ 14 goto :python_too_new

set PYTHON=python
echo   Found: Python !PYVER!
goto :python_ok

:python_too_new
echo   Python !PYVER! is too new ^(no PyTorch wheels available yet^).
echo   PyTorch requires Python 3.12 or 3.13.
echo   Looking for Python 3.12...
:: Try the py launcher (installed with python.org / winget Python)
py -3.12 -c "import sys; sys.exit(0)" >nul 2>&1
if not errorlevel 1 (
    set "PYTHON=py -3.12"
    for /f "tokens=2 delims= " %%v in ('py -3.12 --version 2^>^&1') do echo   Found: Python %%v
    goto :python_ok
)
:: Install Python 3.12 alongside the existing version
echo   Python 3.12 not found. Installing via winget...
winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
if errorlevel 1 (
    echo.
    echo   ERROR: Could not install Python 3.12 automatically.
    echo   PyTorch requires Python 3.12 or 3.13.
    echo   Please install Python 3.12 from https://www.python.org/downloads/
    echo   Then re-run this script.
    echo.
    pause
    exit /b 1
)
set "PATH=%LOCALAPPDATA%\Programs\Python\Python312\;%LOCALAPPDATA%\Programs\Python\Python312\Scripts\;!PATH!"
py -3.12 -c "import sys; sys.exit(0)" >nul 2>&1
if not errorlevel 1 (
    set "PYTHON=py -3.12"
    for /f "tokens=2 delims= " %%v in ('py -3.12 --version 2^>^&1') do echo   Installed: Python %%v
    goto :python_ok
)
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    echo   Using: Python 3.12 ^(direct path^)
    goto :python_ok
)
echo.
echo   ERROR: Python 3.12 was installed but cannot be found.
echo   Close this window and re-run setup-win.bat.
echo.
pause
exit /b 1

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
    echo   ^(or restart your computer^).
    echo.
    pause
    exit /b 1
)
set PYTHON=python
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do echo   Installed: Python %%v

:python_ok
echo.

:: ── Step 3: Check Visual C++ Runtime ────────────────────────────
echo [3/7] Checking Visual C++ Runtime...
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
echo [4/7] Checking virtual environment...
set VENV_OK=0
if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe -c "import sys; sys.exit(0)" >nul 2>&1
    if not errorlevel 1 set VENV_OK=1
)
:: Ensure existing venv Python is compatible with PyTorch (< 3.14)
if "!VENV_OK!"=="1" (
    set "VENV_PY_MINOR=0"
    for /f %%m in ('.venv\Scripts\python.exe -c "import sys; print(sys.version_info.minor)" 2^>nul') do set "VENV_PY_MINOR=%%m"
    if !VENV_PY_MINOR! GEQ 14 (
        echo   Existing venv uses Python 3.!VENV_PY_MINOR! ^(no PyTorch wheels^). Recreating...
        set VENV_OK=0
    )
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
    echo   Created.
)
echo.

:: ── Step 5: Install PyTorch ─────────────────────────────────────
echo   Upgrading pip...
.venv\Scripts\python.exe -m pip install --upgrade pip

:: Detect Python version in venv (affects which PyTorch wheels are available)
set VENV_PYVER=
for /f "tokens=2 delims= " %%v in ('.venv\Scripts\python.exe --version 2^>^&1') do set VENV_PYVER=%%v
echo   Python in venv: !VENV_PYVER!

:: Pick CUDA index based on Python version
:: cu121 has wheels for Python 3.8-3.12; cu124 adds Python 3.13+
set CUDA_INDEX=https://download.pytorch.org/whl/cu121
set CUDA_LABEL=cu121
for /f "tokens=1,2 delims=." %%a in ("!VENV_PYVER!") do (
    if %%b GEQ 13 (
        set CUDA_INDEX=https://download.pytorch.org/whl/cu124
        set CUDA_LABEL=cu124
        echo   Python 3.13+ detected - using CUDA 12.4 index for wheel compatibility.
    )
)

set TORCH_OK=0
if "!GPU_OK!"=="1" (
    echo [5/7] Installing PyTorch with CUDA support ^(!CUDA_LABEL!^)...
    echo   ^(This may take several minutes - ~2.5 GB download^)
    echo.
    .venv\Scripts\pip.exe install torch torchaudio --index-url !CUDA_INDEX!
    if not errorlevel 1 set TORCH_OK=1
    :: Fallback: try the other CUDA index
    if "!TORCH_OK!"=="0" (
        if "!CUDA_LABEL!"=="cu121" (
            echo.
            echo   cu121 install failed. Trying cu124...
            echo.
            .venv\Scripts\pip.exe install torch torchaudio --index-url https://download.pytorch.org/whl/cu124
            if not errorlevel 1 set TORCH_OK=1
        ) else (
            echo.
            echo   cu124 install failed. Trying cu121...
            echo.
            .venv\Scripts\pip.exe install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
            if not errorlevel 1 set TORCH_OK=1
        )
    )
    :: Last resort: CPU-only
    if "!TORCH_OK!"=="0" (
        echo.
        echo   CUDA PyTorch install failed. Trying CPU-only version...
        echo.
        .venv\Scripts\pip.exe install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
        if not errorlevel 1 set TORCH_OK=1
    )
) else (
    echo [5/7] Installing PyTorch ^(CPU-only^)...
    echo   ^(This may take a few minutes^)
    echo.
    .venv\Scripts\pip.exe install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
    if not errorlevel 1 set TORCH_OK=1
)
if "!TORCH_OK!"=="0" (
    echo.
    echo   ERROR: PyTorch installation failed.
    echo   Python version: !VENV_PYVER!
    echo   - Check your internet connection
    echo   - Make sure antivirus isn't blocking downloads
    echo   - If Python 3.13+, try installing Python 3.12 instead
    echo   - Try running this script again
    echo.
    pause
    exit /b 1
)
echo.

:: ── Step 6: Install remaining dependencies ──────────────────────
echo [6/7] Installing dependencies...
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
:: CUDA libraries for faster-whisper (ctranslate2 needs these to find CUDA DLLs)
if "!GPU_OK!"=="1" (
    echo   Installing CUDA libraries for Whisper...
    .venv\Scripts\pip.exe install nvidia-cublas-cu12 nvidia-cudnn-cu12 nvidia-cuda-runtime-cu12 --quiet
)
echo.

:: ── Step 7: Verify installation ─────────────────────────────────
echo [7/7] Verifying installation...
echo.

:: Check core package imports
.venv\Scripts\python.exe -c "import faster_whisper; import sounddevice; import pynput; print('  Core packages: OK')" 2>nul
if errorlevel 1 (
    echo   WARNING: Some core packages may not have installed correctly.
    echo   Bark might still work. Check dictation.log if it crashes.
)

:: Check CUDA status from Python (the real test)
.venv\Scripts\python.exe -c "import torch; c=torch.cuda.is_available(); print('  CUDA: YES - '+torch.cuda.get_device_name(0) if c else '  CUDA: NO (CPU mode)')" 2>nul
if errorlevel 1 (
    echo   WARNING: Could not verify PyTorch installation.
)

:: Warn if GPU was detected in step 1 but CUDA isn't working in Python
if "!GPU_OK!"=="1" (
    .venv\Scripts\python.exe -c "import torch; exit(0 if torch.cuda.is_available() else 1)" >nul 2>&1
    if errorlevel 1 (
        echo.
        echo   NOTE: NVIDIA GPU was detected but CUDA is not available in Python.
        echo   This usually means the NVIDIA driver needs updating.
        echo   Update from: https://www.nvidia.com/drivers
        echo   Bark will still work in CPU mode ^(slower transcription^).
    )
)
echo.

:: ── Write version marker (used by start.bat to detect updates) ──
if exist "VERSION" (
    copy /y VERSION .setup-version >nul
) else (
    echo unknown> .setup-version
)

:: ── Write diagnostic log (share with support if issues arise) ──
(
    echo Bark Setup Diagnostics - %date% %time%
    echo ----------------------------------------
    echo Windows: %OS% %PROCESSOR_ARCHITECTURE%
    echo GPU detected: !GPU_OK! ^(!GPU_NAME!^)
    echo Python: !VENV_PYVER!
    echo CUDA index: !CUDA_LABEL!
    .venv\Scripts\python.exe -c "import torch; print(f'PyTorch: {torch.__version__}'); print(f'CUDA build: {torch.version.cuda}'); print(f'CUDA available: {torch.cuda.is_available()}'); print(f'GPU: {torch.cuda.get_device_name(0)}' if torch.cuda.is_available() else 'GPU: N/A')" 2>&1
    .venv\Scripts\python.exe -c "import faster_whisper; print(f'faster-whisper: OK')" 2>&1
    echo ----------------------------------------
) > setup.log 2>&1

:: ── Done ────────────────────────────────────────────────────────
if "!GPU_OK!"=="1" (
    echo   ========================================
    echo     Setup complete! ^(GPU: !GPU_NAME!^)
) else (
    echo   ========================================
    echo     Setup complete! ^(CPU mode^)
)
echo.
echo     First launch: the Whisper model
echo     downloads automatically ^(~1.5 GB^).
echo   ========================================
echo.
echo   Press any key to launch Bark...
pause >nul
start "" .venv\Scripts\pythonw.exe dictation.py
