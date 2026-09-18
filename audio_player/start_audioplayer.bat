@echo off
REM ============================================================
REM  AudioPlayer - start the audio server app
REM  Usage:  start_audioplayer.bat            (normal window)
REM          start_audioplayer.bat /min       (minimized)
REM
REM  Install to start automatically at Windows login (power-cycle
REM  safe):  run install_startup.bat once, or run this file with
REM  the /install switch:  start_audioplayer.bat /install
REM ============================================================
setlocal
cd /d "%~dp0"

if /i "%~1"=="/install" goto :install
if /i "%~1"=="/uninstall" goto :uninstall

REM ---- run the server -------------------------------------------------------
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

:install
REM ---- register a logon task so the app auto-starts after a power cycle -----
schtasks /Create /F /SC ONLOGON /TN "AudioPlayerServer" ^
  /TR "\"%~f0\" /min" ^
  /RL LIMITED
if %errorlevel%==0 (
  echo Installed: AudioPlayerServer will start at every logon.
  echo Task runs minimized; audio streaming starts per your Schedule plans.
) else (
  echo Failed to create scheduled task. Try running as Administrator.
)
pause
goto :eof

:uninstall
schtasks /Delete /F /TN "AudioPlayerServer" >nul 2>nul
echo Removed the AudioPlayerServer logon task (if it existed).
pause
