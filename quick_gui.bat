@echo off
echo.
echo ==========================================
echo   🎨 Quick GUI Launch - Classic Interface
echo ==========================================
echo.

REM Change to the correct directory
cd /d "c:\Temp\Garmin_RSD_releases\testing new design"

REM Use Anaconda environment for better compatibility
echo ✅ Using Anaconda Python...
C:\Users\feste\anaconda3\Scripts\conda.exe run -p C:\Users\feste\anaconda3 python studio_gui_engines_v3_14.py

echo.
echo GUI session ended.
pause