@echo off
REM Forward to root launcher
cd /d "%~dp0\.."
call "build-desktop-exe.bat" %*
exit /b %ERRORLEVEL%
