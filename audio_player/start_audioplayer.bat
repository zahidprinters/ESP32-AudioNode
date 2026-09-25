@echo off
REM =====================================================================
REM  AudioNode PC server - one-click launcher.
REM
REM  Double-click this file. It starts the server and opens the web
REM  UI in your browser. Leave the window open while you listen.
REM
REM  TO STOP IT: press Ctrl+C in this window (or just close the
REM  window). Both shut the server down; nothing keeps running.
REM
REM  Switches:
REM    /min    start quietly without opening a browser - used by the
REM            Windows logon/startup task, so no browser pops up
REM            when the machine starts.
REM
REM  To start it automatically at logon or at boot:
REM    powershell -ExecutionPolicy Bypass -File install_startup.ps1
REM    powershell -ExecutionPolicy Bypass -File install_startup.ps1 -AtStartup
REM  To remove that again:
REM    powershell -ExecutionPolicy Bypass -File uninstall_startup.ps1
REM =====================================================================
setlocal
REM Run from the repository root: audio_player/ IS the package directory,
REM so "python -m audio_player.app" only resolves one level above it.
cd /d "%~dp0.."
title AudioNode Server

set "URL=http://localhost:5000"
set "OPENUI=1"
if /i "%~1"=="/min" set "OPENUI=0"

REM ---- pick ONE interpreter ----------------------------------------------
REM Order: a .venv next to this repo, then the first python on PATH, then
REM the py launcher. Always resolved to a full path: "python" on PATH is
REM not the same interpreter in every shell (the ESP-IDF venv shadows it),
REM and only this one is guaranteed to have the server's packages.
set "PYEXE="
if exist "%CD%\.venv\Scripts\python.exe" set "PYEXE=%CD%\.venv\Scripts\python.exe"
if not defined PYEXE for /f "delims=" %%p in ('where python 2^>nul') do if not defined PYEXE set "PYEXE=%%p"
if not defined PYEXE for /f "delims=" %%p in ('py -3 -c "import sys;print(sys.executable)" 2^>nul') do if not defined PYEXE set "PYEXE=%%p"
if not defined PYEXE goto no_python

REM ---- that interpreter must actually have the packages ------------------
REM Checked up front so a missing install produces one clear line
REM instead of a ModuleNotFoundError from deep inside the server.
"%PYEXE%" -c "import flask, flask_socketio, imageio_ffmpeg, numpy" >nul 2>nul
if errorlevel 1 goto no_deps

echo.
echo   AudioNode PC server
echo   -------------------------------------------------
echo   Web UI : %URL%
echo   Stop   : press Ctrl+C in this window, or close it
echo.
if "%OPENUI%"=="1" echo   To auto-start at logon, run install_startup.ps1.
echo   Starting - keep this window open while you listen.
echo.

REM ---- open the UI once the server has had a moment to bind the port ------
if "%OPENUI%"=="1" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 4; Start-Process '%URL%'" >nul 2>nul

"%PYEXE%" -m audio_player.app

echo.
echo   AudioNode server stopped.
if "%OPENUI%"=="1" pause
goto :eof

:no_python
echo.
echo   ERROR: no Python interpreter was found.
echo   Install Python 3.11 or newer from python.org, tick
echo   "Add python.exe to PATH", then run this file again.
goto failed

:no_deps
echo.
echo   ERROR: this Python is missing the packages the server needs.
echo.
echo   Interpreter: %PYEXE%
echo   Fix it with:
echo.
echo       "%PYEXE%" -m pip install -r requirements.txt
echo.
echo   then run this file again.
goto failed

:failed
if "%OPENUI%"=="1" pause
exit /b 1
