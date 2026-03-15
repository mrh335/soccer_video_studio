@echo off
setlocal

set SCRIPT_DIR=%~dp0
set PYTHONUTF8=1

if exist "%SCRIPT_DIR%\.venv\Scripts\python.exe" (
  set PYTHON_EXE=%SCRIPT_DIR%\.venv\Scripts\python.exe
) else (
  set PYTHON_EXE=python
)

echo Launching Goalie Highlight Tool GUI...
"%PYTHON_EXE%" "%SCRIPT_DIR%tools\highlight_gui.py"

if errorlevel 1 (
  echo.
  echo The GUI failed to start.
  echo Ensure dependencies are installed:
  echo   pip install pyside6 opencv-python numpy
  pause
)

endlocal
