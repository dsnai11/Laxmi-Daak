@echo off
title CourierTrack Pro - Setup and Run
color 0A

echo.
echo  ==========================================
echo   🚚 CourierTrack Pro - Setup and Launch
echo  ==========================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found! Please install Python 3.9+ from python.org
    pause
    exit /b 1
)

echo [1/4] Python found! OK

:: Install dependencies
echo [2/4] Installing Python dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies!
    pause
    exit /b 1
)
echo Dependencies installed! OK

:: Create directories
if not exist "app\static\uploads" mkdir "app\static\uploads"
if not exist "app\static\qr" mkdir "app\static\qr"
echo Directories created! OK

:: Run the application
echo.
echo [3/4] Starting CourierTrack Pro...
echo.
echo  ==========================================
echo   Open browser: http://localhost:5000
echo   First run: admin password is printed in this console
echo   Press Ctrl+C to stop the server
echo  ==========================================
echo.

python run.py

pause
