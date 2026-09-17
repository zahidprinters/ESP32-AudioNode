# ESP32 AudioNode — WiFi speaker box

A **networked speaker box**: an ESP32-S3 board that joins your WiFi, receives PCM audio over RTP/UDP from a server on the same network, and plays it out through a MAX98357A class-D amp.

**One-time setup**: power the board on → it runs a setup WiFi AP → connect your phone/laptop to it → open the web page → enter your WiFi + server address → the board switches to your network and listens for RTP. From then on it plays whenever the server is sending.

**Multiple nodes**: run the same server stream to several boards (unicast to each board IP:port). One transmitter, many speakers.

## Hardware

| Component | Model | Notes |
|---|---|---|
| Board | ESP32-S3-DevKitC-1-N8R2 | 8 MB flash, 8 MB octal PSRAM |
| Amp | MAX98357A | 3 W class-D, I2S digital input, mono |
| RGB LED | WS2812 | Onboard, GPIO 48 — connection state + audio VU |
| Speaker | — | Connected to MAX98357A OUT+/OUT- |

### Pin connections (MAX98357A ↔ ESP32-S3)

| MAX98357A | ESP32-S3 |
|---|---|
| BCLK      | GPIO 4   |
| LRC       | GPIO 5   |
| DIN       | GPIO 6   |
| SD        | GPIO 15  (driven HIGH = amp enabled) |
| VIN       | 5V       |
| GND       | GND      |

If powering the amp from a separate 5 V supply, **tie the supply GND to the board GND**.
If the SD pin is at VDD, the MAX98357A is at its minimum gain (3 dB) — board digital gain x2 (+6 dB) compensates.

### Audio format

- 48 000 Hz, 16-bit, mono
- I2S Philips-standard, no MCLK (amp derives its own clock)
- Digital gain x2 (+6 dB) on the board; sender decodes with headroom to avoid clipping

## What it does

1. **First boot / factory reset**: board runs a setup WiFi AP named AudioNode-Setup (open, no password) with a captive portal.
2. **Setup**: connect to the AP → open the web page → enter WiFi SSID/password + server IP + port → Save & Connect. Board saves to NVS, joins WiFi, starts RTP listener on port 1234. If WiFi fails within ~30 s → stays in setup AP (NVS kept).
3. **Normal operation**: RGB LED = red (WiFi down) / blue breathing (waiting) / VU meter (streaming). On packet loss, plays silence for missing frames — no glitches.
4. **Factory reset**: hold BOOT (GPIO0) ~5 s after power-on → erase NVS → reboot to setup AP. WiFi drops do NOT erase NVS.

## Product concept

A configurable, networkable speaker — drop it on any WiFi, point it at a server, and it plays. The transport is RTP L16 over UDP (48 kHz, 16-bit, mono, 20 ms frames, PT=96). The audio pipeline (I2S, PSRAM ring buffer, DMA-backpressure pump, ×2 gain, RGB LED, 2-second boot tone) is carried from the proven TCP prototype; only the transport layer changes (TCP → UDP + RTP).

## Repository layout

```
esp32-audio-node/
├── firmware/            # ESP32 firmware (main, CMake, sdkconfig)
├── audio_player/        # PC server app: browser UI + RTP sender
│   ├── app.py           #   Flask + Socket.IO backend (python -m audio_player.app)
│   ├── player.py        #   ffmpeg -> RTP L16/UDP pipeline
│   ├── library.py       #   media folder scan + ffprobe durations
│   ├── config.py        #   paths, nodes, RTP constants
│   ├── selftest.py      #   python -m audio_player.selftest (29 checks)
│   ├── send_pcm.py      #   CLI sender (file / loop / tone), no browser needed
│   ├── templates/       #   UI HTML
│   ├── static/          #   UI js/css
│   └── media/           #   default library root
├── docs/                # README, ARCHITECTURE, SETUP, GUIDELINES,
│                        # CHANGELOG, PROJECT_STATE
├── logs/                # session logs
├── tmp/                 # scratch (git-ignored)
└── env.ps1              # ESP-IDF v6.1 environment (PowerShell)
```

## Protocol at a glance

**RTP L16 over UDP** — 48 kHz, 16-bit, mono, 20 ms frames.

```
PCM 16-bit LE, 48000 Hz, mono, 20 ms/frame = 960 samples = 1920 bytes/frame
RTP: Version=2, PT=96, Seq: +1/frame, Timestamp: +960/frame (samples), SSRC=random
UDP: destination = board IP :1234, source IP = configured server IP (whitelist)
```

The board validates every datagram (version, PT, length, source IP, seq/timestamp) before feeding PCM to the jitter ring buffer. Missing packets → silence fill. Never block I2S on a missing UDP packet.

See ARCHITECTURE.md for the full spec, SETUP.md for running the sender.

## Quick start

```powershell
. D:\esp-idf\tools\env.ps1
cd esp32-audio-node/firmware
idf.py set-target esp32s3
idf.py build
idf.py -p COM5 flash
idf.py -p COM5 monitor --no-reset   # COM5 = board, never COM3
```

Then connect to the AudioNode-Setup WiFi AP, open the portal, enter your WiFi + server, and play either way:

```powershell
# GUI (browser) — pick a file, play/seek/volume
python -m audio_player.app            # from d:\esp-idf -> http://localhost:5000

# or the CLI sender
python audio_player\send_pcm.py file "song.mp3" <board-ip> 1234
```

## Proven building blocks (carried from TCP prototype)

- M0: 1 kHz serial tone via I2S (user verified by ear)
- M1: WiFi STA, power-save OFF (IP <board-ip>, RSSI -34..-41)
- M3: streaming 11,520,000 bytes / 120.0 s, 0 drops, 0 errors (user-confirmed, 2026-09-10)
- PSRAM octal ring buffer (65 KB) stable under 2-min continuous load
- DMA-backpressure pump (no fixed sleep — caused periodic glitches)
- ×2 digital gain (x4 clipped)
- RGB LED: red/blue-breathing/VU, 2 s boot tone

TCP prototype is archived in git history. See CHANGELOG.md.

## Architecture documents

All docs live in `docs/`:

- HARDWARE.md — this file (overview, hardware, quick start, proven blocks)
- ARCHITECTURE.md — full data flow, protocol, packet validation, I2S byte-order, loss handling, factory reset, multi-node
- SETUP.md — server-side setup, Python sender usage, the browser app, VLC alternative, firewall
- GUIDELINES.md — development guidelines, repository layout, decisions and reasons, acceptance criteria, session protocol, toolchain
- PROJECT_STATE.md — live status, feature map, verified working, tried-and-failed, error log
- CHANGELOG.md — chronological change log with commit references
- .cline/rules/esp32-audio-node.md — essentials (single source of truth, read before every session)

## Server side (the other half)

`audio_player/` is the PC-side server: a browser GUI (library picker, play/stop,
seek, volume) plus the same ffmpeg→RTP pipeline the CLI sender uses. It needs
only Python 3 + ffmpeg (via `imageio-ffmpeg`). See SETUP.md.
