@echo off
setlocal enabledelayedexpansion

REM Always run from the folder where this BAT lives:
cd /d "%~dp0"

REM Prefer a local venv if present; otherwise use system python
set PY=python
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

REM Ensure engine modules are importable
set "PYTHONPATH=%CD%\engine;%PYTHONPATH%"

echo === Launching GUI ===
echo   Base: %CD%
echo   Python: %PY%
echo   PYTHONPATH: %PYTHONPATH%
echo.

REM sanity check Python
"%PY%" -V || (
  echo ERROR: Python not found. Install Python 3.10+ and try again.
  echo Press any key to close...
  pause >nul
  exit /b 1
)

REM run the GUI
"%PY%" "studio_gui_engines_v3_14.py"
set ERR=%ERRORLEVEL%

echo.
echo === GUI exited with code %ERR% ===
echo Press any key to close...
pause >nul
exit /b %ERR%
