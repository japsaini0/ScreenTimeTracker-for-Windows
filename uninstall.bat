@echo off
setlocal
title Screen Time Tracker - Uninstaller
echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║    Screen Time Tracker - Uninstaller         ║
echo  ╚══════════════════════════════════════════════╝
echo.

set "APP_NAME=ScreenTimeTracker"
set "INSTALL_DIR=%LOCALAPPDATA%\ScreenTimeTracker"
set "DATA_DIR=%APPDATA%\ScreenTimeTracker"
set "STARTUP_REG=HKCU\Software\Microsoft\Windows\CurrentVersion\Run"

:: Kill running instance
echo  [1/5] Closing running instances...
taskkill /f /im "ScreenTimeTracker.exe" >nul 2>&1
timeout /t 1 /nobreak >nul

:: Remove startup entry
echo  [2/5] Removing from startup...
reg delete "%STARTUP_REG%" /v "%APP_NAME%" /f >nul 2>&1

:: Remove shortcuts
echo  [3/5] Removing shortcuts...
del "%USERPROFILE%\Desktop\Screen Time Tracker.lnk" >nul 2>&1
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Screen Time Tracker.lnk" >nul 2>&1

:: Remove install directory
echo  [4/5] Removing application files...
if exist "%INSTALL_DIR%" rmdir /s /q "%INSTALL_DIR%"

:: Ask about data
echo  [5/5] Data cleanup...
echo.
set /p DELDATA="  Delete screen time data? (y/N): "
if /i "%DELDATA%"=="y" (
    if exist "%DATA_DIR%" rmdir /s /q "%DATA_DIR%"
    echo        Data deleted.
) else (
    echo        Data preserved at: %DATA_DIR%
)

echo.
echo  Uninstallation complete.
pause
