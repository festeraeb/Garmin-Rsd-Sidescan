@echo off
echo.
echo ==========================================
echo   🏔️ 3D Competitive Viewer Launch
echo   Professional Bathymetric Visualization
echo ==========================================
echo.

REM Change to the correct directory
cd /d "c:\Temp\Garmin_RSD_releases\testing new design"

echo 🚀 Features in this viewer:
echo   ✅ Interactive 3D bathymetric mapping
echo   ✅ Multi-format file support
echo   ✅ Professional export (KML, XYZ)
echo   ✅ Target detection integration
echo   ✅ Real-time waterfall display
echo.
echo 💡 Tip: Use File > Open to load any sonar format
echo.

REM Use Anaconda environment for matplotlib support
echo ✅ Using Anaconda Python (matplotlib available)
C:\Users\feste\anaconda3\Scripts\conda.exe run -p C:\Users\feste\anaconda3 python competitive_3d_viewer.py

echo.
echo 3D Viewer session ended.
pause