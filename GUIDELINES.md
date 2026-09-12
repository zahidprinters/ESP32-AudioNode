# Guidelines — AudioNode development

## How to use these guidelines

These are the working rules for this project: what exists, what's proven, how to test, how to commit, and why decisions were made. Read before any change. Update after any change.

## Toolchain

**ESP-IDF v6.1** at `D:\esp32\v6.1\esp-idf`, tools at `C:\Espressif\tools` (EIM install — `export.bat` does NOT work).

Single canonical environment: `D:\esp-idf\env.ps1` (PowerShell).
```powershell
. D:\esp-idf\env.ps1
cd d:\esp-idf\audio_node
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
4. Start the server (Python sender in the desired submode).
5. Observe + listen. Log the session to `logs/<date>_<milestone>.md`.
6. Verify by ear + PC microphone when needed (proven method: tone/noise ratio ~99x on the boot tone).
7. Works → mark ✅ in PROJECT_STATE.md §3, update §8 next steps → **commit** (`M<x>: <what works> (verified on hardware)`).
8. Fails → do NOT commit. Record exact error + approach in PROJECT_STATE §4/§5. Try a DIFFERENT approach (never repeat a failed one).

**Kill zombie processes between tests**: `taskkill /F /IM python.exe /T` and kill any monitor wrappers. Verify 0 python processes before each test. Stale senders poison tests — they keep feeding the board unfiltered audio, making fixes appear not to work.

## What does NOT block the audio task

- The I2S/pump task must never wait on network.
- RX task (UDP recv) and audio task are separate. RX fills the ring; audio pulls from the ring.
- WiFi reconnection, LED updates, network retries — all in their own tasks or throttled so they don't starve the pump.
- Board-side logging: throttled (1 per 5 s for TCP progress in the prototype) so USB CDC printf doesn't flood and starve the pump.

## Commit policy

- Commit **only verified working states** (compiled + flashed + observed OK on hardware).
- Message format: `M<x>: <one-line what works> (verified on hardware)`.
- If a fix fails → revert or try a different approach → update PROJECT_STATE §4/§5. Don't commit broken states.

## File hygiene

- One canonical file per purpose. Never duplicate scripts/tests under new names. `send_pcm.py` stays `send_pcm.py`; `main.c` stays `main/main.c`.
- Experiments/scratch → `tmp/` (git-ignored, periodically deleted). Never in the code tree.
- Logs → `logs/`. Old/abandoned files get deleted, not renamed.
- Before creating any file: check PROJECT_STATE §2 + existing tree; extend existing files instead of adding new ones.

## Anti-patterns (never do)

- Re-trying a known-failed approach (check PROJECT_STATE §4 first).
- Re-writing code that already exists (check feature map first).
- Batching many changes before one build.
- "It compiles" = "it works" — hardware observation required.
- Blitcopy network bytes to I2S without explicit conversion.
- Blocking the audio task on a missing UDP packet.
- Erasing NVS on WiFi failure (only the 5-second BOOT hold erases config).

## Archive — TCP prototype

The TCP implementation (raw PCM over TCP, M0–M3) is archived, not deleted:
- Git history retains all TCP commits (M0 through M4).
- PROJECT_STATE.md §3 records verified TCP milestones.
- The audio pipeline is preserved and reused in the RTP build.
- The transport layer is replaced (TCP → UDP + RTP + validation).

The TCP path proved the audio hardware works end to end. The RTP path is the product transport.