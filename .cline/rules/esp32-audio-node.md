# WORKFLOW SYSTEM (mandatory — read .cline/rules/workflow.md and PROJECT_STATE.md before ANY task)
# Update PROJECT_STATE.md with micro-level detail after every change, build, flash, and test.
# Minimal change → build → flash → log → verify → commit (only if verified on hardware).
# Commit only verified working states; if a fix fails, log it and try a different approach.
# Verify milestones in order: serial tone → WiFi → RTP UDP receiver → streaming. Use PC mic for audio verification.

# ESP32 AUDIO NODE — ESSENTIALS (single source of truth)

## ESP-IDF (installed, use this — not Arduino)
- **IDF v6.1 at `D:\esp32\v6.1\esp-idf`** (current, verified)
- Tools/env at `C:\Espressif\tools` (v6.1: xtensa-esp-elf, python venv v6.1)
- Environment (Windows, canonical):
  ```powershell
  . D:\esp-idf\tools\env.ps1
  ```
  `env.ps1` sets IDF_PATH, toolchain, Python venv, CCACHE, ESP_IDF_VERSION — it mirrors
  `C:\Espressif\tools\Microsoft.v6.1.PowerShell_profile.ps1` (the official EIM profile).
  `export.bat` from the IDF tree does NOT work (EIM install layout is different).
- Build commands (from `d:\esp-idf\firmware`):
  ```powershell
  idf.py set-target esp32s3
  idf.py build
  idf.py -p COM5 flash        (if it can't connect: hold BOOT, tap RESET, release BOOT)
  idf.py -p COM5 monitor --no-reset
  ```
- COM5 = board (USB Serial Device). COM3 = Intel AMT motherboard port — NEVER use.
- Board quirk: USB CDC console sometimes dies after flashing → unplug/replug USB fixes it.
  If board shows "waiting for download" → unplug/replug USB (no buttons).
  Or: with COM5 free, `python -m esptool --chip esp32s3 -p COM5 run` then `idf.py -p COM5 monitor --no-reset`.
- Zombie senders/monitors poison tests — ALWAYS `taskkill /F /IM python.exe /T` before each test.

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

If powering the amp from a separate 5 V supply, **tie the supply GND to the board GND**.
If the SD pin is left at VDD, the MAX98357A is at its minimum gain (3 dB) — digital gain x2 (+6 dB) on the board compensates.

## Setup & config
- First boot / factory reset → board runs setup AP `AudioNode-Setup` (open, no password).
- Connect to the AP → open http://192.168.4.1 → enter WiFi SSID/password + server IP + port → Save & Connect.
- Board saves to NVS → joins WiFi → starts RTP listener on 1234. Failure within ~30 s → stays in setup AP (NVS kept).
- Factory reset: hold BOOT (GPIO0) ~5 s after power-on → erase NVS → reboot to setup AP.
- WiFi drop does NOT erase NVS — board auto-reconnects, LED turns red.

## Audio format
- 48000 Hz, 16-bit, MONO, I2S Philips standard, no MCLK (amp derives it)
- Transport: **RTP L16 over UDP** (PT=96, 48 kHz, 16-bit, mono, 20 ms frames, ts +960/frame in samples)

## Network (values shown are placeholders — use your own)
- WiFi SSID / password: provisioned at runtime through the setup AP; never commit them
- Board IP (STA mode): assigned by your router's DHCP — read it from the serial log
- UDP port 1234 — sender sends RTP to board :1234
- Board = UDP listener (server sends TO the board)

## Proven facts (do not re-litigate)
- Max98357A needs no MCLK; SD HIGH = enabled; VIN on 5V
- I2S pump must be real-time rate-limited (never spin); WiFi power-save OFF
- Jitter buffer in PSRAM; flush on stream end so audio stops promptly
- Clean tone verified via mic test (tone/noise ratio ~99x)
- UDP/RTP is the production transport: validate every datagram (v=2, PT=96, source IP whitelist, seq/ts); silence-fill on loss; never block I2S waiting for a missing packet
- Board = UDP listener (server sends TO the board); source IP validated against configured server IP

## Documentation references
- `README.md` — project overview, hardware, quick start, proven building blocks
- `ARCHITECTURE.md` — full data flow, RTP protocol spec, packet validation, loss handling, I2S byte-order, WiFi modes, factory reset, multi-node
- `SETUP.md` — server-side setup (Windows/Mac/Linux), sender usage (file/loop/tone), VLC alternative, firewall, multi-node
- `GUIDELINES.md` — toolchain, build/flash/test loop, commit policy, file hygiene, anti-patterns, TCP archive
- `PROJECT_STATE.md` — live status, feature map, verified working, tried-and-failed, decisions, next steps

## Session protocol (before any change)
1. READ `PROJECT_STATE.md` — know what exists, what failed, what's next.
2. Make the smallest possible change. One idea per build.
3. Build (`idf.py build`), flash (`idf.py -p COM5 flash`), test, log to `logs/`, commit only if verified on hardware.
