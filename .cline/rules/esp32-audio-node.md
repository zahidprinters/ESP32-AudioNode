# WORKFLOW SYSTEM (mandatory — read .cline/rules/workflow.md and PROJECT_STATE.md before ANY task)
# Update PROJECT_STATE.md with micro-level detail after every change, build, flash, and test.
# Minimal change → build → flash → log → verify → commit (only if verified on hardware).
# Commit only verified working states; if a fix fails, log it and try a different approach.
# Verify milestones in order: serial tone → WiFi → TCP → streaming. Use PC mic for audio verification.

# ESP32 AUDIO NODE — ESSENTIALS (single source of truth)

## ESP-IDF (installed, use this — not Arduino)
- **IDF v6.1 at `D:\esp32\v6.1\esp-idf`** (current, verified)
- Tools/env at `C:\Espressif\tools` (v6.1: xtensa-esp-elf, python venv v6.1)
- Build commands (run in cmd):
  call D:\esp32\v6.1\esp-idf\export.bat
  cd /d d:\esp-idf\audio_node
  idf.py set-target esp32s3
  idf.py build
  idf.py -p COM5 flash        (if it can't connect: hold BOOT, tap RESET, release BOOT)
  idf.py -p COM5 monitor --no-reset
- COM5 = board (USB Serial Device). COM3 = Intel AMT motherboard port — NEVER use.
- Board quirk: USB CDC console sometimes dies after flashing → unplug/replug USB fixes it.
  If board shows "waiting for download" → unplug/replug USB (no buttons).

## Hardware
- Board: ESP32-S3-DevKitC-1-N8R2 (8MB flash, 8MB octal PSRAM)
- Amp: MAX98357A (mono, 3W class-D). Speaker on amp OUT+/OUT-

## Pin connections (unchanged — verified working)
| MAX98357A | ESP32-S3 |
|-----------|----------|
| BCLK      | GPIO 4   |
| LRC       | GPIO 5   |
| DIN       | GPIO 6   |
| SD        | GPIO 15  (driven HIGH = amp enabled) |
| VIN       | 5V       |
| GND       | GND      |

## Audio format
- 48000 Hz, 16-bit, MONO, I2S Philips standard, no MCLK (amp derives it)
- Transport: raw PCM over TCP (UDP lost ~25% packets on this AP)

## Network
- WiFi SSID: `<ssid>`  Password: `<password>`
- Board IP: <board-ip> (RSSI -32..-40 dBm = excellent)
- PC (server) IP: <pc-ip>, TCP port 1234 (firewall rules exist)
- Board connects TO the PC (client mode), sender waits in accept()

## Proven facts (do not re-litigate)
- Max98357A needs no MCLK; SD HIGH = enabled; VIN on 5V
- I2S pump must be real-time rate-limited (never spin); WiFi power-save OFF
- Jitter buffer in PSRAM; flush on stream end so audio stops promptly
- Clean tone verified via mic test (tone/noise ratio ~99x)
