# Tech Context

## Stack

| Layer | Technology | Version | Notes |
|---|---|---|---|
| Board | ESP32-S3-DevKitC-1-N8R2 | — | WROOM-1 module, 8 MB flash, **8 MB octal** PSRAM |
| Firmware | ESP-IDF | **6.1** | `d:\esp32\v6.1\esp-idf`; EIM layout, so `export.bat` does not work — use `tools\env.ps1` |
| Component | `espressif/led_strip` | ^3.0.0 | in `managed_components/`, pinned by `dependencies.lock` |
| Amplifier | MAX98357A | — | I2S in, speaker out; no MCLK, 3 dB min gain at SD=VDD |
| Server | Python + Flask + Flask-SocketIO | 3.11.9 | `requirements.txt`; `imageio-ffmpeg` supplies ffmpeg |
| Toolchain | xtensa-esp-elf, ninja, cmake | 15.2.0 / 4.0.3 | under `C:\Espressif\tools` |

PSRAM is **8 MB octal**, not the 2 MB of an N8R2's quad cousin: `sdkconfig.defaults`
pins `CONFIG_SPIRAM_MODE_OCT=y`, and the jitter ring lives there.

## Setup

```powershell
# from the repository root
. tools\env.ps1
cd firmware
idf.py build
idf.py -p COM5 flash          # COM5 = the board. COM3 = Intel AMT, never flash it.
idf.py -p COM5 monitor --no-reset
```

`idf.py monitor` is interactive and will hang a non-interactive shell. For a
scripted boot log:

```powershell
python "$env:USERPROFILE\.cline\tools\serial_capture.py" COM5 30 > logs\boot.log
```

## Constraints
- **Audio format is not negotiable:** 48 kHz, 16-bit, mono, 20 ms frames,
  960 samples = 1920 bytes, payload type 96, sequence +1, timestamp +960.
- PSRAM is required for the audio ring buffer; the board is an N8R2 variant.
- Audio I2S and the WS2812 LED both compete for timing — the VU-meter animation
  must not block the I2S pump.
- `idf.py mcp-server` does not exist in 6.1 either, and must not be promised —
  the terminal is the interface.

## External services
| Service | Why | Failure looks like |
|---|---|---|
| Board setup AP | first-boot provisioning | phone/computer sees no `AudioNode-Setup` SSID |
| LAN UDP | RTP stream | server shows sending, board LED never shows VU |

## Tooling
| Command | Does |
|---|---|
| `python -m audio_player.selftest` | no-framework self-check, exits non-zero on failure |
| `python audio_player\send_pcm.py tone <board-ip> 1234 30 1000 0.5` | bench tone through the amp |
| `powershell -File audio_player\install_startup.ps1 -AtStartup` | register the logon task |
| `python "$env:USERPROFILE\.cline\tools\serial_capture.py" COM5 30` | non-interactive boot log |
