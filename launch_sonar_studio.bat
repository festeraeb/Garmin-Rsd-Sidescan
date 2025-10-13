@echo off
echo.
echo ==========================================
echo   🚀 Advanced Sonar Studio Launcher
echo   Market-Disrupting Multi-Format System
echo ==========================================
echo.
echo 🎯 Features Available:
echo   ✅ 18x Rust acceleration
echo   ✅ Universal format support
echo   ✅ AI target detection
echo   ✅ 3D visualization
echo   ✅ Professional exports
echo.

REM Change to the correct directory
cd /d "c:\Temp\Garmin_RSD_releases\testing new design"

REM Use Anaconda environment for better package support
echo 🔍 Checking Python environment...
echo ✅ Using Anaconda Python (recommended for matplotlib/numpy)
set PYTHON_CMD=C:\Users\feste\anaconda3\Scripts\conda.exe run -p C:\Users\feste\anaconda3 python

REM Check if required files exist
echo 🔍 Checking system files...
if not exist "studio_gui_engines_v3_14.py" (
    echo ❌ Main GUI file not found!
    pause
    exit /b 1
)

if not exist "competitive_3d_viewer.py" (
    echo ❌ 3D Viewer not found!
    pause
    exit /b 1
)

if not exist "parsers\base_parser.py" (
    echo ❌ Parser system not found!
    pause
    exit /b 1
)

echo ✅ All system files found
echo.

REM Display menu
echo ==========================================
echo   Choose Your Launch Option:
echo ==========================================
echo   1. 🎨 Classic GUI (Original System)
echo   2. 🏔️  3D Competitive Viewer (New!)
echo   3. 🎯 Target Detection Demo
echo   4. 🦀 Rust Performance Benchmark
echo   5. 📊 Multi-Format Parser Test
echo ==========================================
echo.

set /p choice="Enter your choice (1-5): "

if "%choice%"=="1" (
    echo.
    echo 🎨 Launching Classic Sonar Studio GUI...
    echo.
    %PYTHON_CMD% studio_gui_engines_v3_14.py
    goto end
)

if "%choice%"=="2" (
    echo.
    echo 🏔️ Launching 3D Competitive Viewer...
    echo   💡 Tip: Load any sonar file format for 3D visualization
    echo.
    %PYTHON_CMD% competitive_3d_viewer.py
    goto end
)

if "%choice%"=="3" (
    echo.
    echo 🎯 Running AI Target Detection Demo...
    echo.
    %PYTHON_CMD% advanced_target_detection.py
    goto end
)

if "%choice%"=="4" (
    echo.
    echo 🦀 Running Rust vs Python Performance Benchmark...
    echo.
    %PYTHON_CMD% benchmark_rust_vs_python.py
    goto end
)

if "%choice%"=="5" (
    echo.
    echo 📊 Testing Multi-Format Parser Support...
    echo.
    %PYTHON_CMD% test_real_files.py
    goto end
)

echo ❌ Invalid choice. Please run the script again.

:end
echo.
echo ==========================================
echo   Session Complete - Thank you! 🌊
echo ==========================================
pause