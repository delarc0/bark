@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo ERROR: Virtual environment not found. Run setup first.
    pause
    exit /b 1
)
start "" .venv\Scripts\pythonw.exe dictation.py
