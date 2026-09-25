# env.ps1 — ESP-IDF v6.1 environment for THIS machine.
# Machine-specific by design: the paths below describe one EIM (Espressif
# Installation Manager) layout. On any other machine activate your own ESP-IDF
# environment, or edit the IDF_PATH / IDF_TOOLS_PATH values here to match.
# Mirrors C:\Espressif\tools\Microsoft.v6.1.PowerShell_profile.ps1.
# Usage:  . D:\esp-idf\tools\env.ps1   then run: idf.py build   (from project dir)
$env:IDF_PATH = "d:\esp32\v6.1\esp-idf"
$env:IDF_TOOLS_PATH = "C:\Espressif\tools"
$env:IDF_PYTHON_ENV_PATH = "C:\Espressif\tools\python\v6.1\venv"
$env:ESP_ROM_ELF_DIR = "C:\Espressif\tools\esp-rom-elfs\20241011\"
$env:IDF_CCACHE_ENABLE = "1"
$env:ESP_IDF_VERSION = "6.1"
$env:IDF_VERSION = "6.1.0"
$env:IDF_COMPONENT_LOCAL_STORAGE_URL = "file://C:\Espressif\tools"
$env:PATH = "C:\Espressif\tools\ccache\4.12.1\ccache-4.12.1-windows-x86_64;C:\Espressif\tools\cmake\4.0.3\bin;C:\Espressif\tools\dfu-util\0.11\dfu-util-0.11-win64;C:\Espressif\tools\ninja\1.12.1\;C:\Espressif\tools\xtensa-esp-elf\esp-15.2.0_20251204\xtensa-esp-elf\bin;C:\Espressif\tools\riscv32-esp-elf\esp-15.2.0_20251204\riscv32-esp-elf\bin;C:\Espressif\tools\esp32ulp-elf\2.38_20240113\esp32ulp-elf\bin;C:\Espressif\tools\openocd-esp32\v0.12.0-esp32-20260703\openocd-esp32\bin;C:\Espressif\tools\python\v6.1\venv\Scripts;$env:PATH"
function global:idfpy { & "C:\Espressif\tools\python\v6.1\venv\Scripts\python.exe" "d:\esp32\v6.1\esp-idf\tools\idf.py" @args }
Set-Alias -Name idf.py -Value idfpy -Scope Global -Force
Write-Host "ESP-IDF v6.1 env ready (IDF_PATH=$env:IDF_PATH)"
