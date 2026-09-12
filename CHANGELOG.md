# Changelog

All notable changes to the **AudioNode WiFi speaker box** project are documented here.
Format: latest first. Each entry maps to a git commit. See each doc file (README, ARCHITECTURE, etc.) for current state.

---

## [unreleased] — RTP/UDP product phase

### Added
- **Documentation set**: `README.md`, `ARCHITECTURE.md`, `SERVER_SETUP.md`, `GUIDELINES.md` — full product documentation for the RTP/UDP phase.
- **RTP L16 protocol spec** in ARCHITECTURE.md: 48 kHz, 16-bit, mono, 20 ms frames, PT=96, seq+1/frame, timestamp +960 in samples.
- **Packet validation spec**: version=2, PT=96, length, source-IP whitelist, seq/ts sanity checks before ring buffer.
- **Loss handling spec**: silence-fill on packet loss, never block I2S on missing UDP.
- **Setup flow spec**: setup AP (`AudioNode-Setup`), captive portal, NVS config, STA mode, WiFi failover.
- **Factory reset spec**: GPIO0 (BOOT button) held ~5 s → NVS erase → setup AP. WiFi loss does NOT erase NVS.

### Changed
- **Protocol**: TCP → RTP L16 over UDP (production transport). TCP prototype preserved in git history.
- **`.cline/rules/esp32-audio-node.md`**: milestone order (TCP→RTP UDP receiver), build commands (`env.ps1` instead of `export.bat`), transport (TCP→RTP UDP), network (TCP→UDP), added Setup & config section, GND tie note, proven facts updated.
- **`.cline/rules/workflow.md`**: milestone order (TCP→RTP UDP receiver).
- **`PROJECT_STATE.md`**: §1 focus → RTP/UDP phase; §2 feature map P1–P10 (TCP milestones archived); §3 verified (TCP marked archived); §6 decisions & reasons; §8 acceptance criteria; §11 next steps reordered.

### Planned (next implementation phase)
- P1: RTP UDP receiver + validation in `main.c` (preserve I2S/ring/pump/gain/LED).
- P2+P3: Setup AP + captive portal + NVS config + STA mode + WiFi failover.
- P4: Factory reset (GPIO0).
- P8: Rewrite `send_pcm.py` → RTP UDP sender (file/loop/tone submodes).

---

## 2026-09-10 — M4: MP3 file streaming + audio quality (archived)

### Added
- `file` mode in `send_pcm.py` — decode any audio file via ffmpeg (imageio-ffmpeg static) to 48 kHz/16-bit/mono PCM, stream in real time.
- `loop` mode in `send_pcm.py` — WASAPI loopback (pyaudiowpatch) for VLC/PC-speaker mirroring.
- RGB LED VU meter (green→yellow→red by level) on WS2812 GPIO48.
- Connection-state LED: red (WiFi down) / blue breathing (waiting) / VU (streaming).

### Fixed
- **Volume too low**: SD pin at VDD = amp's 3 dB minimum gain → ×2 digital gain (+6 dB). x4 attempt clipped → reverted to x2.
- **Jerky playback with monitor attached**: pump wrote 21.3 ms chunks (1024 frames) instead of 5.3 ms; tcp progress logs throttled to 1/5 s; 170 ms prefill before play starts.
- **Pump pacing regression**: 14 ms fixed sleep caused periodic long tones → back to 4 ms (DMA backpressure).
- **Power-on tone**: limited to ~2 seconds, then silence.
- **Audio quality**: highpass 180 Hz + bass shelf -16 dB + compressor + limiter + volume 0.30 (board ×2 gain → 0.60 peak, below clipping).

### Known
- Bass peaks from MAX98357A can sag shared USB 5 V rail → recommendation: separate 5 V amp supply with common GND.

---

## 2026-09-08 — M0–M3: TCP prototype (archived)

### Added
- **M0**: 1 kHz serial tone via I2S on MAX98357A — clean, verified by ear.
- **M1**: WiFi STA, power-save OFF — IP <board-ip>, RSSI -34..-41 dBm.
- **M2**: TCP client → PC server accept (port 1234), connection held.
- **M3**: Raw PCM TCP stream via PSRAM ring buffer — 120.0 s / 11,520,000 bytes, 0 drops, 0 recv errors, prompt stop on stream end (user-confirmed).
- PSRAM octal ring buffer as jitter cushion.
- TCP no-drop discipline: pause recv when ring nearly full.

### Discovered
- Board download-mode quirk: `esptool -p COM5 run` + `monitor --no-reset` recovers without unplugging.
- Zombie senders/monitors poison tests — always `taskkill /F /IM python.exe /T` before each run.

---

### Legend
- ✅ DONE = verified on hardware
- 🚧 DESIGN = design complete, not yet implemented
- 🔲 TODO = not started
