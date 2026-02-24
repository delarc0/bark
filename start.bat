@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

:: Check if setup needs to run:
:: 1. No venv at all (fresh install)
:: 2. Version mismatch (update installed new files but setup didn't re-run)
set NEED_SETUP=0

if not exist ".venv\Scripts\pythonw.exe" set NEED_SETUP=1

if "!NEED_SETUP!"=="0" (
    set SETUP_VER=
    if exist ".setup-version" set /p SETUP_VER=<.setup-version
    set APP_VER=
    if exist "VERSION" set /p APP_VER=<VERSION
    if "!SETUP_VER!" neq "!APP_VER!" set NEED_SETUP=1
)

if "!NEED_SETUP!"=="1" (
    echo Bark setup required. Running now...
    echo.
    if exist "%~dp0setup-win.bat" (
        call "%~dp0setup-win.bat"
    ) else if exist "%~dp0installer\setup-win.bat" (
        call "%~dp0installer\setup-win.bat"
    ) else (
        echo ERROR: setup-win.bat not found.
        echo Re-download Bark from https://github.com/delarc0/bark
        pause
        exit /b 1
    )
    if not exist ".venv\Scripts\pythonw.exe" (
        echo ERROR: Setup failed. See errors above.
        pause
        exit /b 1
    )
)

start "" .venv\Scripts\pythonw.exe dictation.py
