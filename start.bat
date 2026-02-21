@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo Bark is not set up yet. Running setup now...
    echo.
    if exist "%~dp0setup-win.bat" (
        call "%~dp0setup-win.bat"
    ) else if exist "%~dp0installer\setup-win.bat" (
        call "%~dp0installer\setup-win.bat"
    )
    if not exist ".venv\Scripts\pythonw.exe" (
        echo ERROR: Setup failed. See errors above.
        pause
        exit /b 1
    )
)
start "" .venv\Scripts\pythonw.exe dictation.py
