@echo off
REM ============================================================
REM  AudioPlayer - start the audio server
REM  Usage:  start_audioplayer.bat          (normal window)
REM          start_audioplayer.bat /min     (minimized)
REM
REM  To start it automatically at logon or at boot, use the scheduled
REM  task instead - it is the single supported mechanism:
REM      powershell -ExecutionPolicy Bypass -File install_startup.ps1
REM      powershell -ExecutionPolicy Bypass -File install_startup.ps1 -AtStartup
REM      powershell -ExecutionPolicy Bypass -File uninstall_startup.ps1
REM ============================================================
setlocal
cd /d "%~dp0"

REM Find python on PATH; fall back to the py launcher.
where python >nul 2>nul
if %errorlevel%==0 (
  if /i "%~1"=="/min" (
    start "AudioPlayer" /min python -m audio_player.app
  ) else (
    python -m audio_player.app
  )
) else (
  if /i "%~1"=="/min" (
    start "AudioPlayer" /min py -m audio_player.app
  ) else (
    py -m audio_player.app
  )
)
goto :eof
