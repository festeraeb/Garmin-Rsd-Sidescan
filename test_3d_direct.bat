@echo off
echo.
echo ==========================================
echo   🏔️ 3D Viewer - Direct Launch Test
echo ==========================================
echo.

cd /d "c:\Temp\Garmin_RSD_releases\testing new design"

echo Testing Python environment...
python -c "import sys; print('Python:', sys.executable)"

echo.
echo Installing matplotlib if needed...
python -m pip install matplotlib numpy pillow tkinter

echo.
echo Testing matplotlib import...
python -c "import matplotlib.pyplot as plt; print('✅ matplotlib works!')"

echo.
echo Launching 3D viewer...
python competitive_3d_viewer.py

pause