@echo off
REM ====================================================================
REM Garmin RSD Studio - Windows Launcher with Environment Setup
REM Professional Marine Survey Analysis
REM Contact: festeraeb@yahoo.com for licensing
REM ====================================================================

echo.
echo ==========================================
echo  🌊 Garmin RSD Studio - Beta Launch  
echo ==========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ ERROR: Python is not installed or not in PATH
    echo.
    echo Please install Python 3.8+ from: https://python.org
    echo Make sure to check "Add Python to PATH" during installation
    echo.
    pause
    exit /b 1
)

REM Display Python version
echo ✅ Python detected:
python --version

REM Check if we're in the right directory
if not exist "studio_gui_engines_v3_14.py" (
    echo.
    echo ❌ ERROR: studio_gui_engines_v3_14.py not found
    echo Please run this script from the Garmin RSD Studio directory
    echo.
    pause
    exit /b 1
)

echo.
echo 📦 Checking dependencies...

REM Check if requirements.txt exists
if not exist "requirements.txt" (
    echo ❌ requirements.txt not found - creating minimal requirements
    echo tkinter > requirements.txt
    echo numpy >> requirements.txt
    echo matplotlib >> requirements.txt
)

REM Install/update dependencies
echo Installing required packages...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo.
    echo ⚠️  Some packages may have failed to install
    echo Continuing with available packages...
    echo.
)

echo.
echo 🚀 Launching Garmin RSD Studio...
echo.

REM Launch the application
python studio_gui_engines_v3_14.py

REM Check exit code
if %errorlevel% neq 0 (
    echo.
    echo ❌ Application exited with error code: %errorlevel%
    echo.
    echo 📧 For support, contact: festeraeb@yahoo.com
    echo 🆘 SAR Groups: FREE licensing available
    echo 💼 Commercial: One-time purchase (no yearly fees)
    echo.
    pause
    exit /b %errorlevel%
)

echo.
echo ✅ Garmin RSD Studio closed successfully
echo.
echo 📧 For licensing and support: festeraeb@yahoo.com
echo 🆘 SAR Groups: FREE licensing available  
echo 💼 Commercial: One-time purchase licensing
echo.
pause