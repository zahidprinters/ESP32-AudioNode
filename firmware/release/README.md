
# Shipped firmware BIN — scope (planned)

This file will live in `firmware/release/` alongside the shipped production BIN and `firmware-version.json`. It is not yet populated; the first release ships the BIN for the exact board/amp/pinout this repo supports. The doc exists now so the BIN's scope is honest when it ships.

## What the first release BIN is

- **Board**: ESP32-S3-DevKitC-1-N8R2 (8 MB flash, 8 MB octal PSRAM)
- **Amp**: MAX98357A (mono, 3 W class-D), VIN on 5 V, GND common.
- **Pinout (fixed for this BIN)**:
  - BCLK = GPIO 4
  - LRC  = GPIO 5
  - DIN  = GPIO 6
  - SD   = GPIO 15 (amp enabled; HIGH = on)
- **Audio**: 48000 Hz, 16-bit, mono, I2S Philips standard, no MCLK (amp derives it).
- **Transport**: RTP L16 over UDP (PT=96, 48 kHz, 16-bit, mono, 20 ms frames, ts +960 samples/frame), listener on UDP 1234.

## What it is NOT (first release)

- It is **not** a universal BIN for arbitrary ESP32 boards or other pinouts.
- It does **not** require the user to have the ESP-IDF toolchain on their PC — it is pre-built and shipped with the installer.

## How it is used

- The installer puts this BIN and a `firmware-version.json` into the app's data dir.
- The in-app flash panel drives esptool to write it to the board (user picks COM port, confirms, explicit action — never automatic).
- The board then runs the firmware's setup AP / STA-from-NVS / streaming paths as documented in the project overview.

## Regenerating

- Source: `firmware/` (ESP-IDF C). Building from source requires the full ESP-IDF toolchain on the machine (see docs/GUIDELINES.md). That is an **advanced / later** path, not the default one-click path.

## Future

- Other boards / other pinouts → later: ship multiple BIN variants or add an optional full-IDF rebuild path.
- Online "check latest BIN" → later: soft check against a hosted version file / GitHub release; offline default; never required.
