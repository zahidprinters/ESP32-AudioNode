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

REM ---- pick an interpreter that ACTUALLY HAS the packages ----------------
REM A .venv in this repo wins outright. Otherwise try every python on PATH
REM and take the first one that can import them: "python" is not the same
REM interpreter in every shell (sourcing the ESP-IDF environment puts its
REM own venv, which has no flask, in front of the real one).
REM audio_player/deps.py owns the list, so this can never drift from what
REM the server itself requires.
set "PYEXE="
if exist "%CD%\.venv\Scripts\python.exe" set "PYEXE=%CD%\.venv\Scripts\python.exe"
if not defined PYEXE for /f "delims=" %%p in ('where python 2^>nul') do if not defined PYEXE call :usable "%%p"
if not defined PYEXE for /f "delims=" %%p in ('py -3 -c "import sys;print(sys.executable)" 2^>nul') do if not defined PYEXE call :usable "%%p"
if not defined PYEXE goto no_usable

REM Records this start in logs\app.log, and catches anything :usable missed.
"%PYEXE%" -c "from audio_player.deps import ensure; import sys; sys.exit(0 if ensure() else 1)"

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

REM ---- subroutine: keep %PYEXE% only if this interpreter can import them --
:usable
if defined PYEXE goto :eof
"%~1" -c "from audio_player.deps import missing; import sys; sys.exit(0 if not missing() else 1)" >nul 2>nul && set "PYEXE=%~1"
goto :eof

REM ---- no candidate worked: explain precisely which case this is ---------
:no_usable
set "PYEXE="
for /f "delims=" %%p in ('where python 2^>nul') do if not defined PYEXE set "PYEXE=%%p"
if not defined PYEXE for /f "delims=" %%p in ('py -3 -c "import sys;print(sys.executable)" 2^>nul') do if not defined PYEXE set "PYEXE=%%p"
if not defined PYEXE goto no_python
REM A Python exists but is missing packages: let deps.py say exactly which.
"%PYEXE%" -c "from audio_player.deps import ensure; import sys; sys.exit(0 if ensure() else 1)" >nul
goto failed

:no_python
echo.
echo   ERROR: no Python interpreter was found on this machine.
echo   Install Python 3.11 or newer from python.org, tick
echo   "Add python.exe to PATH", then run this file again.
goto failed

:failed
echo   The server was not started. The reason is above and was recorded
echo   in logs\app.log.
echo.
echo   To install the missing packages into this Python:
echo.
echo       "%PYEXE%" -m audio_player.app --install-deps
echo.
echo   then run this file again.
if "%OPENUI%"=="1" pause
exit /b 1
