@echo off
:: Build Bark-Setup.exe from bark-installer.iss
:: Requires: Inno Setup 6 (https://jrsoftware.org/isdl.php)

cd /d "%~dp0"

set ISCC=
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
) else if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
)

if "%ISCC%"=="" (
    echo ERROR: Inno Setup 6 not found.
    echo Download from: https://jrsoftware.org/isdl.php
    echo.
    pause
    exit /b 1
)

echo Building Bark-Setup.exe...
echo.
"%ISCC%" bark-installer.iss
if errorlevel 1 (
    echo.
    echo Build failed.
    pause
    exit /b 1
)

echo.
echo Done! Output: build\Bark-Setup.exe
echo.
pause
