# Guidelines — AudioNode development

## How to use these guidelines

These are the working rules for this project: what exists, what's proven, how to test, how to commit, and why decisions were made. Read before any change. Update after any change.

## Toolchain

**ESP-IDF v6.1** at `D:\esp32\v6.1\esp-idf`, tools at `C:\Espressif\tools` (EIM install — `export.bat` does NOT work).

Single canonical environment: `D:\esp-idf\tools\env.ps1` (PowerShell).
```powershell
. D:\esp-idf\tools\env.ps1
cd d:\esp-idf\firmware
idf.py set-target esp32s3
idf.py build
idf.py -p COM5 flash
idf.py -p COM5 monitor --no-reset
```

COM5 = board (USB Serial Device). **Never COM3** — that's the Intel AMT motherboard port.

**Board quirks (never re-litigate)**:
- USB CDC console can die after flashing → unplug/replug USB fixes it.
- If board shows "waiting for download" → unplug/replug USB (no buttons).
- Download-mode recovery (no unplug needed): with COM5 free, run `python -m esptool --chip esp32s3 -p COM5 run` then `idf.py -p COM5 monitor --no-reset`. The harness runs esptool FIRST, then monitor (never concurrently — port conflict).

## Protocol (production)

**RTP L16 over UDP** — 48 kHz, 16-bit, mono, 20 ms frames.

- Frame: 960 samples = 1 920 PCM bytes.
- RTP: version=2, PT=96, seq +1/frame, ts +960/frame (samples, not ms), SSRC = random per sender.
- UDP destination: board IP :1234. Source IP must equal the configured server IP.
- Receiver validates every datagram (version, PT, length, source IP, seq/ts sanity) before feeding PCM to the ring buffer. Invalid = discard + silence fill.
- Missing packets: fill silence, never block I2S waiting for a lost UDP packet.

See ARCHITECTURE.md for the full spec.

## Audio pipeline (preserved from TCP prototype)

- I2S: 48 kHz, 16-bit, mono, Philips-standard, no MCLK.
- MAX98357A: BCLK=GPIO4, LRC=GPIO5, DIN=GPIO6, SD=GPIO15 (HIGH=amp on). No MCLK.
- PSRAM octal ring buffer (jitter cushion, 65 KB tested).
- Pump: DMA-backpressure driven, no fixed sleep.
- Gain: ×2 digital (+6 dB) on the board. Sender decodes with headroom.
- LED: WS2812 on GPIO48 — red (WiFi down) / blue breathing (waiting) / VU (streaming).
- Boot: 2-second tone then silence.

## Build / flash / test loop

1. Build (`idf.py build`) — must succeed before flashing. Never flash a stale build.
2. Flash (`idf.py -p COM5 flash`).
3. Monitor (`idf.py -p COM5 monitor --no-reset`) — observe on hardware.
4. Start the server — either the CLI sender (`audio_player/send_pcm.py`) or the GUI app (`python -m audio_player.app`).
5. Observe + listen. Log the session to `logs/<date>_<milestone>.md`.
6. Verify by ear + PC microphone when needed (proven method: tone/noise ratio ~99x on the boot tone).
7. Works → mark ✅ in PROJECT_STATE.md §3, update §8 next steps → **commit** (`M<x>: <what works> (verified on hardware)` for firmware; `M<x>: <what works> (verified)` for app/server changes that don't touch firmware).
8. Fails → do NOT commit. Record exact error + approach in PROJECT_STATE §4/§5. Try a DIFFERENT approach (never repeat a failed one).

**Kill zombie processes between tests**: `taskkill /F /IM python.exe /T` and kill any monitor wrappers. Verify 0 python processes before each test. Stale senders poison tests — they keep feeding the board unfiltered audio, making fixes appear not to work.

## What does NOT block the audio task

- The I2S/pump task must never wait on network.
- RX task (UDP recv) and audio task are separate. RX fills the ring; audio pulls from the ring.
- WiFi reconnection, LED updates, network retries — all in their own tasks or throttled so they don't starve the pump.
- Board-side logging: throttled so USB CDC printf doesn't flood and starve the pump.

## Commit policy

- Commit **only verified working states** (compiled + flashed + observed OK on hardware for firmware; started + exercised + verified for the app).
- Message format: `M<x>: <one-line what works> (verified on hardware)`.
- If a fix fails → revert or try a different approach → update PROJECT_STATE §4/§5. Don't commit broken states.

## File hygiene

- One canonical file per purpose. `send_pcm.py` stays `send_pcm.py`; `main.c` stays `firmware/main/main.c`; the app stays in `audio_player/`.
- Experiments/scratch → `tmp/` (git-ignored, periodically deleted). Never in the code tree.
- Logs → `logs/`. Old/abandoned files get deleted, not renamed.
- Before creating any file: check PROJECT_STATE §2 + existing tree; extend existing files instead of adding new ones.

## Anti-patterns (never do)

- Re-trying a known-failed approach (check PROJECT_STATE §4 first).
- Re-writing code that already exists (check feature map first).
- Batching many changes before one build.
- "It compiles" = "it works" — hardware observation required.
- Blitcopy network bytes to I2S without explicit conversion (except where the wire format is already the target's native endian; this project's RTP L16 payload is LE and ESP32-S3 is LE, so no swap needed).
- Blocking the audio task on a missing UDP packet.
- Erasing NVS on WiFi failure (only the 5-second BOOT hold erases config).

## Archive — TCP prototype

The TCP implementation (raw PCM over TCP, M0–M3) is archived, not deleted:
- Git history retains all TCP commits (M0 through M4).
- PROJECT_STATE.md §3 records verified TCP milestones.
- The audio pipeline is preserved and reused in the RTP build.
- The transport layer is replaced (TCP → UDP + RTP + validation).

The TCP path proved the audio hardware works end to end. The RTP path is the product transport.

**Known ceilings (documented in code + here)**:
- MP3 seek is ffmpeg-dependent, not sample-accurate to the sample — fine for a seek bar, not for frame-locked editing.
- Volume change restarts the ffmpeg pipeline (ffmpeg volume is an input filter) — a brief gap on volume drag; acceptable for V1.
- WS server uses eventlet (deprecated). Fine for an internal V1 tool; migration to gevent/asyncio is a noted future cleanup, not a blocker.
- Frame-accurate multi-node sync is explicitly out of V1 — when we get there it's a known hard problem (clock drift across ESP32s), flagged in ARCHITECTURE.md.
- The app is Windows-first today. Linux/macOS run the same `python -m audio_player.app` as long as ffmpeg (imageio-ffmpeg) is installed; the only Windows-only piece is `audio_player/send_pcm.py` loop mode, not the app.

The TCP path proved the audio hardware works end to end. The RTP path is the product transport.


## Repository layout

```

esp32-audio-node/
├── firmware/                 # ESP32 firmware (ESP-IDF v6.1, target esp32s3)
│   ├── main/main.c           # app_main + WiFi/RTP/UDP receiver + setup AP + factory reset
│   ├── main/CMakeLists.txt
│   ├── main/idf_component.yml
│   ├── CMakeLists.txt
│   ├── sdkconfig.defaults     # PSRAM octal, IP reassembly (frames > MTU), IP_REASS_MAX_PBUFS=20
│   ├── sdkconfig             # generated — do not edit by hand
│   ├── managed_components/
│   └── dependencies.lock
│
├── audio_player/             # server-side GUI app (this machine = server during dev)
│   ├── app.py                # Flask + Socket.IO backend (`python -m audio_player.app`)
│   ├── player.py             # the single ffmpeg -> RTP L16/UDP pipeline (+ pacing)
│   ├── library.py            # media folder scan + ffprobe durations
│   ├── config.py             # paths, nodes, RTP constants
│   ├── selftest.py           # `python -m audio_player.selftest` — 29 asserts, no framework
│   ├── send_pcm.py           # standalone CLI sender (file / loop / tone)
│   ├── static/               # app.js, style.css
│   ├── templates/            # index.html
│   └── media/                # MP3 files (copied in for dev; UI can point elsewhere)
│
├── docs/                   # all project documentation
│   ├── HARDWARE.md         # hardware, overview, development history
│   ├── ARCHITECTURE.md
│   ├── SETUP.md
│   ├── GUIDELINES.md      # this file
│   ├── CHANGELOG.md       # repo-level change log
│   └── PROJECT_STATE.md
│
├── README.md             # project overview, quick start, node setup, checks
├── pyproject.toml        # packaging metadata (`pip install -e .`)
├── requirements.txt      # minimum dependency versions (not a lockfile)
├── tools/env.ps1        # ESP-IDF v6.1 environment (PowerShell) — only needed for firmware builds
├── .gitignore
├── logs/                 # session logs
└── tmp/                  # scratch (git-ignored)

```

Two independent products live in this repo, kept strictly separate:

- **firmware/** — the ESP32 speaker-box firmware. Built with `idf.py build` from `firmware/`. Flashed to the board. Talks RTP L16/UDP only; has no MP3 decoding, no playlist logic, no persistence of playback state.
- **audio_player/** — the server-side GUI app that runs on the server machine. Decodes MP3 → RTP L16/UDP, serves the browser UI, tracks position/volume. Talks to the boards over UDP only (same wire format the CLI sender uses).

They connect only over the network (UDP datagrams to board IP :1234). Do not mix their code — firmware code stays in firmware/, app code stays in audio_player/.

### Audio Player App (audio_player/)

A browser-based control panel that runs on the server machine and streams audio to one or more ESP32 AudioNode boards over RTP L16/UDP.

**What it is**: the "complete audio system" server — library (MP3 folder), play/stop/volume/seek, per-node status, scheduling (V2+), multi-node (V2+).

**Stack (V1)**: Flask + Flask-SocketIO (eventlet) + ffmpeg (via imageio-ffmpeg static binary, no system install) + a browser on the same machine (or any machine that can reach the server's port 5000).

**Run (V1)**:
```powershell
python -m audio_player.app            # from d:/esp-idf (or any cwd with audio_player on path)
# UI:  http://localhost:5000
```
With a different library root or extra nodes:
```powershell
python -m audio_player.app --library "D:\Music" --node <board-ip>:1234
```

**Config**: `audio_player/config.py` holds defaults (library_root, nodes, default_volume, RTP params, ffmpeg path). The UI can change library_root at runtime (WS `set_library_root`); nodes for V1 are fixed in config (multi-node editing is V2+).

**Wire format**: exactly the same RTP L16/UDP the firmware expects and the CLI sender (`audio_player/send_pcm.py`) uses — 48 kHz, 16-bit, mono, 20 ms frames, PT=96, seq+1/frame, ts+960/frame, UDP to each node IP :1234. The app reuses the proven ffmpeg→RTP path from `send_pcm.py` file_mode.

**V1 scope (this milestone)**:
- MP3 library (folder scan + duration via ffprobe).
- Play / stop / volume slider / position seek bar (seek = ffmpeg restart at the target sample).
- One node (<board-ip>:1234) — the board we have on the desk.
- Node status shown in the UI = server-side view (is the stream running?). The board has no back-channel today, so "playing" = "we are sending". V2+ adds board-reported confirmation when the firmware gains a back-channel.

**V2+ (not in V1)**:
- Multi-node: add/edit nodes in the UI, stream to N boards.
- Scheduler: daily time window (e.g. 07:00–10:00) → auto-play a playlist; pause outside the window.
- Resume-from-last-position: persist each stream's sample position; on restart seek ffmpeg back to it.
- Board-reported "am I actually playing audio" confirmation (firmware back-channel — future firmware change).
