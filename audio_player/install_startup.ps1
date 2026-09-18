<#
  AudioPlayer - register a Windows Scheduled Task so the server starts
  automatically after a power cycle / logon.

  Run once (no admin needed for a current-user logon task):
      powershell -ExecutionPolicy Bypass -File install_startup.ps1

  Start at boot instead of at logon (needs admin):
      powershell -ExecutionPolicy Bypass -File install_startup.ps1 -AtStartup

  Remove again:
      powershell -ExecutionPolicy Bypass -File uninstall_startup.ps1
#>
param(
    [string]$TaskName = 'AudioPlayer',
    [switch]$AtStartup
)

$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $here                      # repo root (parent of audio_player/)
$bat  = Join-Path $here 'start_audioplayer.bat'

if (-not (Test-Path $bat)) { throw "start_audioplayer.bat not found next to this script: $bat" }

$trigger = if ($AtStartup) { New-ScheduledTaskTrigger -AtStartup }
           else            { New-ScheduledTaskTrigger -AtLogOn }

$action = New-ScheduledTaskAction -Execute 'cmd.exe' `
                                  -Argument ('/c "' + $bat + '"') `
                                  -WorkingDirectory $root

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
                       -Settings $settings -Force | Out-Null

Write-Host "Registered scheduled task '$TaskName'"
Write-Host "  start now : Start-ScheduledTask -TaskName $TaskName"
Write-Host "  remove    : .\uninstall_startup.ps1"
Write-Host "  open UI   : http://localhost:5000"
