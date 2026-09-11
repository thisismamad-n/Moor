@echo off
setlocal EnableDelayedExpansion

REM ============================================================================
REM Moor Desktop Executable Compiler (1-Click Windows Launcher)
REM ============================================================================
REM Double-click this file to compile the Moor desktop application into an .exe.
REM ============================================================================

title Moor Desktop Executable Compiler

REM Ensure working directory is the project root
cd /d "%~dp0"

echo.
echo ==============================================================================
echo  MOOR DESKTOP EXECUTABLE COMPILER
echo ==============================================================================
echo  Project Root: %~dp0
echo.

REM Locate PowerShell executable (prefer modern pwsh, fallback to powershell)
set "PS_CMD="
where pwsh.exe >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set "PS_CMD=pwsh.exe"
) else (
    where powershell.exe >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        set "PS_CMD=powershell.exe"
    )
)

if not defined PS_CMD (
    echo [ERROR] Neither pwsh.exe nor powershell.exe was found in PATH.
    echo         Please install PowerShell or run: python scripts\build_desktop_exe.py
    echo.
    pause
    exit /b 1
)

echo [INFO] Using PowerShell engine: %PS_CMD%
echo [INFO] Starting build script: scripts\build-desktop-exe.ps1
echo [INFO] Offline-first build: repo.zip + install.ps1/sh are staged into
echo [INFO] the .exe automatically (no network needed on first launch).
echo.

REM Execute build script with bypassed execution policy and forward any passed arguments
"%PS_CMD%" -NoProfile -ExecutionPolicy Bypass -File "scripts\build-desktop-exe.ps1" %*

set "BUILD_EXIT_CODE=%ERRORLEVEL%"

echo.
if %BUILD_EXIT_CODE% equ 0 (
    echo ==============================================================================
    echo [OK] Desktop application compiled successfully!
    echo      You can find the output in: apps\desktop\release\
    echo ==============================================================================
) else (
    echo ==============================================================================
    echo [ERROR] Desktop compilation failed with exit code: %BUILD_EXIT_CODE%
    echo         Review the messages above for details.
    echo ==============================================================================
)
echo.

REM Keep command window open so output can be inspected when double-clicked
pause
exit /b %BUILD_EXIT_CODE%
