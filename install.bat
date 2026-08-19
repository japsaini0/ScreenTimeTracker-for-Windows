@echo off
setlocal
title Screen Time Tracker - Installer
echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║    Screen Time Tracker - Installer           ║
echo  ╚══════════════════════════════════════════════╝
echo.

:: Config
set "APP_NAME=ScreenTimeTracker"
set "INSTALL_DIR=%LOCALAPPDATA%\ScreenTimeTracker"
set "EXE_NAME=ScreenTimeTracker.exe"
set "SOURCE_EXE=%~dp0dist\%EXE_NAME%"
set "STARTUP_REG=HKCU\Software\Microsoft\Windows\CurrentVersion\Run"

:: Check if exe exists
if not exist "%SOURCE_EXE%" (
    echo  [ERROR] %EXE_NAME% not found in dist\ folder.
    echo          Run build.bat first to build the executable.
    echo.
    pause
    exit /b 1
)

:: Kill running instance
echo  [1/6] Closing any running instances...
taskkill /f /im "%EXE_NAME%" >nul 2>&1
timeout /t 1 /nobreak >nul

:: Create install directory
echo  [2/6] Creating install directory...
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

:: Copy exe
echo  [3/6] Installing application...
copy /y "%SOURCE_EXE%" "%INSTALL_DIR%\%EXE_NAME%" >nul
if %errorlevel% neq 0 (
    echo  [ERROR] Failed to copy executable. Is the app running?
    pause
    exit /b 1
)
echo        Installed to: %INSTALL_DIR%\%EXE_NAME%

:: Create Desktop shortcut
echo  [4/6] Creating Desktop shortcut...
set "DESKTOP=%USERPROFILE%\Desktop"
set "SHORTCUT_SCRIPT=%TEMP%\create_shortcut.vbs"
(
echo Set oWS = WScript.CreateObject^("WScript.Shell"^)
echo Set oLink = oWS.CreateShortcut^("%DESKTOP%\Screen Time Tracker.lnk"^)
echo oLink.TargetPath = "%INSTALL_DIR%\%EXE_NAME%"
echo oLink.WorkingDirectory = "%INSTALL_DIR%"
echo oLink.Description = "Track your screen time"
echo oLink.Save
) > "%SHORTCUT_SCRIPT%"
cscript //nologo "%SHORTCUT_SCRIPT%"
del "%SHORTCUT_SCRIPT%" >nul 2>&1
echo        Created: %DESKTOP%\Screen Time Tracker.lnk

:: Create Start Menu shortcut
echo  [5/6] Creating Start Menu shortcut...
set "STARTMENU=%APPDATA%\Microsoft\Windows\Start Menu\Programs"
set "SHORTCUT_SCRIPT2=%TEMP%\create_shortcut2.vbs"
(
echo Set oWS = WScript.CreateObject^("WScript.Shell"^)
echo Set oLink = oWS.CreateShortcut^("%STARTMENU%\Screen Time Tracker.lnk"^)
echo oLink.TargetPath = "%INSTALL_DIR%\%EXE_NAME%"
echo oLink.WorkingDirectory = "%INSTALL_DIR%"
echo oLink.Description = "Track your screen time"
echo oLink.Save
) > "%SHORTCUT_SCRIPT2%"
cscript //nologo "%SHORTCUT_SCRIPT2%"
del "%SHORTCUT_SCRIPT2%" >nul 2>&1
echo        Created: Start Menu shortcut

:: Enable startup
echo  [6/6] Enabling auto-start...
reg add "%STARTUP_REG%" /v "%APP_NAME%" /t REG_SZ /d "\"%INSTALL_DIR%\%EXE_NAME%\" --minimized" /f >nul 2>&1
echo        Added to Windows startup

echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║          Installation Complete!              ║
echo  ╠══════════════════════════════════════════════╣
echo  ║                                              ║
echo  ║  Location : %LOCALAPPDATA%\ScreenTimeTracker  
echo  ║  Data     : %APPDATA%\ScreenTimeTracker       
echo  ║  Desktop  : Shortcut created                 ║
echo  ║  Startup  : Enabled (starts minimized)       ║
echo  ║                                              ║
echo  ╚══════════════════════════════════════════════╝
echo.

:: Launch the app
echo  Starting Screen Time Tracker...
start "" "%INSTALL_DIR%\%EXE_NAME%"
echo.
echo  Done! You can close this window.
pause
