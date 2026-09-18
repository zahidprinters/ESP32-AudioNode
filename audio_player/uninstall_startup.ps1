<#
  AudioPlayer - remove the Windows Scheduled Task created by install_startup.ps1.
      powershell -ExecutionPolicy Bypass -File uninstall_startup.ps1
#>
param([string]$TaskName = 'AudioPlayer')

$ErrorActionPreference = 'SilentlyContinue'
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
Write-Host "Removed scheduled task '$TaskName' (if it existed)."
