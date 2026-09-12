# AudioNode — WiFi speaker box

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
d:\esp-idf\
├── audio_node/          # ESP32 firmware (main, CMake, sdkconfig)
├── server/
│   └── send_pcm.py      # cross-platform RTP sender (file / loop / tone)
├── logs/                # session logs
├── tmp/                 # scratch (git-ignored)
├── env.ps1              # ESP-IDF v6.1 environment (PowerShell)
├── README.md            # this file
├── ARCHITECTURE.md      # full architecture + protocol spec
├── SERVER_SETUP.md      # server-side setup, all platforms
├── GUIDELINES.md        # development guidelines + decisions + acceptance
├── CHANGELOG.md         # chronological change log
└── PROJECT_STATE.md     # live status, feature map, next steps
```

## Protocol at a glance

**RTP L16 over UDP** — 48 kHz, 16-bit, mono, 20 ms frames.

```
PCM 16-bit LE, 48000 Hz, mono, 20 ms/frame = 960 samples = 1920 bytes/frame
RTP: Version=2, PT=96, Seq: +1/frame, Timestamp: +960/frame (samples), SSRC=random
UDP: destination = board IP :1234, source IP = configured server IP (whitelist)
```

The board validates every datagram (version, PT, length, source IP, seq/timestamp) before feeding PCM to the jitter ring buffer. Missing packets → silence fill. Never block I2S on a missing UDP packet.

See ARCHITECTURE.md for the full spec, SERVER_SETUP.md for running the sender.

## Quick start

```powershell
. D:\esp-idf\env.ps1
cd d:\esp-idf\audio_node
idf.py set-target esp32s3
idf.py build
idf.py -p COM5 flash
idf.py -p COM5 monitor --no-reset   # COM5 = board, never COM3
```

Then connect to the AudioNode-Setup WiFi AP, open the portal, enter your WiFi + server, and play:

```bash
python send_pcm.py file "song.mp3" <board-ip> 1234
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

- ARCHITECTURE.md — full data flow, protocol, packet validation, I2S byte-order, loss handling, factory reset, multi-node
- SERVER_SETUP.md — server-side setup, Python sender usage, VLC alternative, firewall
- GUIDELINES.md — development guidelines, decisions and reasons, acceptance criteria, session protocol, toolchain
- PROJECT_STATE.md — live status, feature map, verified working, tried-and-failed, error log
- CHANGELOG.md — chronological change log with commit references
- .cline/rules/esp32-audio-node.md — essentials (single source of truth, read before every session)
