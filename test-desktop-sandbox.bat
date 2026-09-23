@echo off
setlocal EnableDelayedExpansion

title Moor Desktop Sandbox Test Launcher

cd /d "%~dp0"

echo ==============================================================================
echo  MOOR DESKTOP SANDBOX TEST LAUNCHER (WINDOWS SANDBOX)
echo ==============================================================================
echo.
echo  This tool launches a fresh, disposable Windows Sandbox environment
echo  with your release folder mounted to test first-launch on a clean PC.
echo.

set "SANDBOX_EXE=%SystemRoot%\System32\WindowsSandbox.exe"

if not exist "!SANDBOX_EXE!" (
    echo [ERROR] WindowsSandbox.exe was not found at: !SANDBOX_EXE!
    echo         Please ensure Windows Sandbox is enabled in Windows Features.
    echo.
    pause
    exit /b 1
)

echo  Available Options:
echo    [1] Launch Sandbox WITH Internet (Online test - normal first-run setup)
echo    [2] Launch Sandbox WITHOUT Internet (Offline test - verifies offline bundle)
echo    [3] Exit
echo.

set /p CHOICE="Enter choice [1, 2, or 3]: "

if "%CHOICE%"=="1" (
    echo.
    echo [INFO] Launching Windows Sandbox in Online mode...
    echo [INFO] Command: "!SANDBOX_EXE!" "%~dp0test-desktop-sandbox-online.wsb"
    start "" "!SANDBOX_EXE!" "%~dp0test-desktop-sandbox-online.wsb"
    if !ERRORLEVEL! neq 0 (
        echo [ERROR] Failed to start Windows Sandbox (Exit code: !ERRORLEVEL!)
        pause
    ) else (
        echo [OK] Windows Sandbox launched. Please wait 15-30 seconds for the window to appear.
        timeout /t 5 >nul
    )
    goto end
)

if "%CHOICE%"=="2" (
    echo.
    echo [INFO] Launching Windows Sandbox in Offline mode...
    echo [INFO] Command: "!SANDBOX_EXE!" "%~dp0test-desktop-sandbox-offline.wsb"
    start "" "!SANDBOX_EXE!" "%~dp0test-desktop-sandbox-offline.wsb"
    if !ERRORLEVEL! neq 0 (
        echo [ERROR] Failed to start Windows Sandbox (Exit code: !ERRORLEVEL!)
        pause
    ) else (
        echo [OK] Windows Sandbox launched. Please wait 15-30 seconds for the window to appear.
        timeout /t 5 >nul
    )
    goto end
)

if "%CHOICE%"=="3" (
    goto end
)

echo.
echo [ERROR] Invalid choice: "%CHOICE%". Please choose 1, 2, or 3.
pause

:end
endlocal
