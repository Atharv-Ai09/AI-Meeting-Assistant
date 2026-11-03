@echo off
setlocal
cd /d "%~dp0"
title AI Meeting Assistant - GTTC Belagavi

echo ==============================================================
echo   AI Meeting Assistant  -  Speech Recognition and Summarization
echo   Developed by Atharv Shetty ^| GTTC Belagavi ^| AI ^& ML
echo ==============================================================

where py >nul 2>nul
if errorlevel 1 goto no_launcher

if exist ".venv\Scripts\python.exe" goto venv_ready

echo.
echo [1/3] Creating virtual environment with Python 3.12 ...
py -3.12 -m venv .venv
if not errorlevel 1 goto install_deps

echo Python 3.12 not found. Trying Python 3.11 ...
rmdir /s /q .venv >nul 2>nul
py -3.11 -m venv .venv
if errorlevel 1 goto no_python

:install_deps
echo.
echo [2/3] Installing dependencies (this can take several minutes) ...
".venv\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto install_failed

:venv_ready
if not exist ".env" copy ".env.example" ".env" >nul

where ffmpeg >nul 2>nul
if errorlevel 1 echo WARNING: FFmpeg was not found on PATH. Install it with: winget install Gyan.FFmpeg  (then reopen the terminal)

echo.
echo [3/3] Starting the application ...
echo Open http://127.0.0.1:5000 in your browser. Press Ctrl+C to stop.
echo The first transcription downloads AI models and may take several minutes.
echo.
".venv\Scripts\python.exe" app.py
goto end

:no_launcher
echo ERROR: The Python launcher "py" was not found.
echo Install Python 3.12 from https://www.python.org/downloads/ and tick "Add python.exe to PATH".
goto end

:no_python
echo ERROR: Python 3.12 or 3.11 is required but was not found.
echo Install Python 3.12 from https://www.python.org/downloads/ and run this file again.
goto end

:install_failed
echo ERROR: Dependency installation failed. Check the messages above and the README troubleshooting section.
rmdir /s /q .venv >nul 2>nul

:end
pause
endlocal
