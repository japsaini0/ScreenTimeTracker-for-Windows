@echo off
echo ========================================
echo   Screen Time Tracker - Build Script
echo ========================================
echo.

echo [1/3] Installing dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)
echo.

echo [2/3] Building executable...
pyinstaller --noconfirm --onefile --windowed ^
    --name "ScreenTimeTracker" ^
    --icon=NONE ^
    --add-data "smart_detect.py;." ^
    --hidden-import=PySide6.QtWidgets ^
    --hidden-import=PySide6.QtCore ^
    --hidden-import=PySide6.QtGui ^
    --hidden-import=win32api ^
    --hidden-import=win32gui ^
    --hidden-import=psutil ^
    main.py

if %errorlevel% neq 0 (
    echo ERROR: Build failed
    pause
    exit /b 1
)
echo.

echo [3/3] Build complete!
echo.
echo Executable location: dist\ScreenTimeTracker.exe
echo.
pause
