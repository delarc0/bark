@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo   Bark Release Builder
echo ============================================================
echo.

:: Activate venv
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo ERROR: .venv not found. Run installer\setup-win.bat first.
    exit /b 1
)

:: Check PyInstaller
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

:: Pre-save Silero VAD model
if not exist "silero_vad.jit" (
    echo Saving Silero VAD model...
    python -c "import torch; m, _ = torch.hub.load('snakers4/silero-vad', 'silero_vad', trust_repo=True); torch.jit.save(m, 'silero_vad.jit'); print('OK')"
    if errorlevel 1 (
        echo ERROR: Failed to save Silero VAD model.
        exit /b 1
    )
) else (
    echo Silero VAD model already exists, skipping.
)

:: Build with PyInstaller
echo.
echo Building with PyInstaller...
pyinstaller bark.spec --clean
if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    exit /b 1
)

:: Verify output
if not exist "dist\Bark\Bark.exe" (
    echo ERROR: dist\Bark\Bark.exe not found after build.
    exit /b 1
)
echo.
echo PyInstaller build OK: dist\Bark\Bark.exe

:: Read version
set /p VERSION=<VERSION
echo Version: %VERSION%

:: Build Inno Setup installer (if ISCC is available)
where iscc >nul 2>&1
if not errorlevel 1 (
    echo.
    echo Building Inno Setup installer...
    iscc installer\bark-installer.iss
    if errorlevel 1 (
        echo WARNING: Inno Setup build failed. The PyInstaller output is still in dist\Bark\
    ) else (
        echo.
        echo Installer ready: installer\build\Bark-%VERSION%-Setup.exe
    )
) else (
    echo.
    echo Inno Setup (iscc) not found in PATH. Skipping installer build.
    echo Install Inno Setup 6 to build the installer, or distribute dist\Bark\ as a zip.
)

echo.
echo ============================================================
echo   Build complete!
echo ============================================================
