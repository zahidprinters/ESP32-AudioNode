# Changelog

All notable changes to the **ESP32 AudioNode** project are documented here.
Format: latest first. Each entry maps to a git commit. See each doc file (README, ARCHITECTURE, etc.) for current state.

---

## [unreleased] — RTP/UDP product phase

### Audit register + roadmap (2026-09-19)
- **`docs/AUDIT.md` added** — living register of external code reviews. Every reported item
  is re-verified against the actual source before it gets a verdict (`✅ done` / `🔲 valid` /
  `⚠️ not a defect` / `❌ rejected or deferred`), with the evidence recorded in an appendix.
- **Round 1 — 32-item firmware review triaged**: 5 already satisfied (including the three
  fixed in the same-day P12 commit), **19 valid**, **5 inaccurate claims**, 3 rejected or
  deferred. The 19 valid items are grouped into six phases with an explicit hardware gate
  each: **A** diagnostics, **B** portal input handling, **C** NVS config versioning,
  **D** stream/timer/handle hygiene, **E** boot & amp hygiene, **F** polish (only against a
  measurement). Phase C is a prerequisite for the `server_port` decision in Phase B.
- **The review's claimed root cause did not hold**: its four "explains your no-IP symptom"
  items were checked on hardware and the node was healthy — `<ssid>` joined,
  `GOT IP: <board-ip>`, first-attempt `bind()`. The node was silent because no sender was
  running. The diagnostics were still adopted, so a *future* failure is not silent.
- **`docs/GUIDELINES.md` de-duplicated** — a previous patch had appended an evolved copy of
  the guideline sections, so sections 7–101 repeated at 188–290 with the unique
  "Repository layout" / "Audio Player App" content wedged between them (a one-line edit
  therefore showed as two identical hunks). Rebuilt losslessly: **290 → 196 lines, 12 unique
  headings**, 6 declared supersessions, zero unexpected line drops.
- **Dead code removed** — `audio_player/config.py` defined `sched_save()` / `sched_load()`
  (added by a previous session's patch script) that nothing imported; schedules are
  persisted through `settings_save()`.

### Repository / publication preparation (2026-09-17)
- **Root `README.md`** added (project overview, PC-app quick start, node connection
  steps, hardware table, checks, security notes); the old root-level overview became
  `docs/HARDWARE.md`.
- **Packaging metadata**: `pyproject.toml` (`pip install -e .`, console script
  `audio-player`, version read dynamically from `audio_player.__version__`),
  `requirements.txt` (minimum versions, not a lockfile), `audio_player/__init__.py`.
- **`.gitattributes`** added: LF in-repo on every platform (`* text=auto eol=lf`),
  binary asset rules, documentation paths excluded from language stats.
- **Credential redaction**: the lab Wi-Fi SSID and development LAN addresses were
  replaced with placeholders (`<ssid>`, `192.168.1.x`, `<board-ip>`) across docs,
  logs and code. The Wi-Fi **password was never committed**. Git history was
  rewritten (`git filter-branch` + expiry + `gc`), then verified: no password and no
  SSID in any reachable commit. All commit hashes changed, so old clones are invalid.
- **Scratch/build artifacts removed** (`a/`, `dist/`, `build/`, `AudioPlayer.egg-info/`,
  unused `audio_player/static/js/help.js`); `.gitignore` extended for raw log dumps,
  `tmp/`, media, `nodes.json` and `eq_presets.json`.
- **License**: MIT (`LICENSE`), declared in `pyproject.toml` via PEP 639
  (`license = "MIT"` + `license-files`).
- **Known remaining exception** (documented in the README): private development LAN
  addresses still appear in historical docs/logs. They are RFC 1918 addresses, not
  credentials, and the Wi-Fi password is absent from every commit.

### Project polish (2026-09-17)
- **Tree finalized**: root holds only project-wide meta-files (`README.md`,
  `CHANGELOG.md`, `LICENSE`, `pyproject.toml`, `requirements.txt`, `env.ps1`,
  `.gitignore`, `.gitattributes`) plus the three components — `firmware/`,
  `audio_player/`, `docs/` — and `logs/` for curated evidence.
- **`CHANGELOG.md` moved to the repository root** (conventional location); all
  references updated.
- **Per-component READMEs added**: `firmware/README.md` (hardware, pins, build/flash
  loop) and `audio_player/README.md` (architecture, REST/Socket.IO API, EQ, CLI).
  One canonical changelog is kept — components point at the root file.
- **Dead code removed**: two unused imports in `audio_player/player.py`.
- **Junk removed**: `tmpREADME.md`, tracked `firmware/sdkconfig.old`, raw log dumps.

### Added
- **`audio_player/` browser app (V1)** — Flask + Flask-SocketIO (eventlet) + ffmpeg
  (`imageio-ffmpeg`). Library picker with ffprobe durations, play/stop/seek/volume,
  live position, per-node readout. **Verified on hardware 2026-09-15**:
  20 s stream → board `pkts=821 dropped=0`, `pcm = pkts × 1920` exactly, 50.0 pkts/s
  (real time), position 1:1 with the wall clock, RSSI −44…−50 dBm.
- **`audio_player/player.py`** — one ffmpeg → RTP L16/UDP pipeline per stream, with
  a shared `rtp_header()` and real-time pacing.
- **`audio_player/selftest.py`** — `python -m audio_player.selftest`, 29 asserts, no
  framework. Includes a pacing regression test that measures the real send rate over
  a loopback UDP socket (~50 frames/s expected; ~150 with the pacing bug).
- **10-band equalizer + presets in the browser app** — VLC band grid (60 Hz…16 kHz)
  + preamp, live-applied by restarting the ffmpeg pipeline at the current position
  (limiter stays last so the board can never clip); built-in presets (Acoustic,
  Bass Booster/Reducer, Classical, Pop, Rock / Metal, Vocal / Voice, Treble Boost,
  Flat, and the speaker-specific Mid Cut) plus named user presets saved to
  `audio_player/eq_presets.json` (git-ignored). Selftest grew EQ-chain checks
  (limiter-last invariant, clamping, preset normalization, save/load round trip).
- **Repository restructure**: `audio_node/` → `firmware/`, all root `*.md` → `docs/`,
  new `audio_player/` app, `server/send_pcm.py` → `audio_player/send_pcm.py`.
- **RTP L16/UDP receiver (P1)** — implemented in `main.c`, **verified on hardware 2026-09-13**: 30 s stream, 1272+ packets, `dropped=0`.
- **Setup AP + captive portal (P2)** — implemented, **verified on hardware 2026-09-13**: empty-NVS boot → open AP `AudioNode-Setup` @192.168.4.1 → form → Save → NVS blob → reboot → STA.
- **STA mode + WiFi failover (P3)** — implemented, **verified on hardware 2026-09-13**: NVS config on boot → joins WiFi → got IP → RTP listener on :1234, power-save OFF.
- **Factory reset (P4)** — implemented in `main.c`, **verified on hardware 2026-09-14**: BOOT/GPIO0 held 5 s → `nvs_flash_erase()` → reboot → setup AP (one clean cycle, no panic).
- **RTP sender (P8)** — `audio_player/send_pcm.py` RTP over UDP with `tone`/`file`/`loop` submodes; used for the P1 verification.
- **Documentation set**: `README.md`, `ARCHITECTURE.md`, `SERVER_SETUP.md`, `GUIDELINES.md` — full product documentation for the RTP/UDP phase.
- **RTP L16 protocol spec** in ARCHITECTURE.md: 48 kHz, 16-bit, mono, 20 ms frames, PT=96, seq+1/frame, timestamp +960 in samples.
- **Packet validation spec**: version=2, PT=96, length, source-IP whitelist, seq/ts sanity checks before ring buffer.
- **Loss handling spec**: silence-fill on packet loss, never block I2S on missing UDP.
- **Setup flow spec**: setup AP (`AudioNode-Setup`), captive portal, NVS config, STA mode, WiFi failover.
- **Factory reset spec**: GPIO0 (BOOT button) held ~5 s → NVS erase → setup AP. WiFi loss does NOT erase NVS.

### Changed
- **Protocol**: TCP → RTP L16 over UDP (production transport). TCP prototype preserved in git history.
- **First-boot behaviour**: removed the factory WiFi seed — an empty NVS now boots straight into `AudioNode-Setup`, matching the documented spec (the seed silently auto-joined the lab WiFi instead).
- **`.cline/rules/esp32-audio-node.md`**, **`.cline/rules/workflow.md`**, **`PROJECT_STATE.md`**: updated for the RTP/UDP phase (build commands via `env.ps1`, milestone order, transport, next steps).

### Fixed
- **Sender free-ran at ~3× real time (app `player.py`)** — the pacing guard
  `if 0 < ahead < 0.1: time.sleep(ahead)` silently disabled pacing the moment the
  sender ran >100 ms ahead (immediate, since ffmpeg hands the pump 4 frames per
  read), so it streamed at ffmpeg's decode rate. Evidence: position advanced
  ~3020 ms per 1000 ms wall clock; board logged `pkts=358 dropped=45`. Fix: anchor
  the pacing clock on the first sent frame and sleep the whole lead, capped per
  iteration → 50.0 pkts/s, `dropped=0`.
- **`/api/status` hung (app `app.py`)** — the 250 ms position loop called
  `_node_status()` while already holding `status_lock`, and `threading.Lock` is not
  reentrant, so the loop deadlocked on its first iteration holding the lock forever.
  Fix: `_nodes_for(state, pos_s)` takes no locks and is called outside the lock.
- **Position lost on any pipeline restart (app `player.py`)** — `seek()` and
  `set_volume()` restart the ffmpeg pipeline and zeroed the byte counter, so a seek
  reported 0:00 and a volume change restarted the song from the beginning. Fix:
  `_base_samples` keeps position absolute across restarts; `set_volume()` now
  restarts at the current position.
- **Finished file stayed "playing" forever (app `player.py`)** — on natural ffmpeg
  EOF the pump reported `stopped` but never cleared `_running`, so `sample_position`
  kept returning the last byte count. Fix: clear `_running` and kill the pipeline.
- **Every RTP frame silently dropped** (`recvfrom` blocked forever while ping still worked): 1932 B frames exceed the 1500 B MTU and arrive IP-fragmented, but `CONFIG_LWIP_IP4_REASSEMBLY` was off. Enabling it and raising `IP_REASS_MAX_PBUFS` 10 → 20 produced `dropped=0`.
- **Setup-AP boot loop**: `esp_netif_set_ip_info()` on the AP netif while its DHCPS was running → `ESP_ERR_ESP_NETIF_DHCP_NOT_STOPPED` panic, reboot, repeat. Fix: stop DHCPS → set IP → restart DHCPS.
- **Boot loop from init order**: `esp_wifi_init()` ran before `nvs_flash_init()` → `ESP_ERR_NVS_NOT_INITIALIZED`. NVS init must come first.
- **Premature failover**: ms/µs unit mismatch opened AP mode ~30 ms after STA start instead of after 30 s.
- **RGB LED stuck solid red after any stream**: the streaming flag (`net_state = 2`) was never cleared when a UDP stream ended (the TCP task's stream-end path was lost in the transport rewrite), and the pump's starved branch skipped the VU update, so `vu_level` froze at its last loud peak (loud = red). Fixed by deriving "streaming" from packet recency (`last_pkt_ms`, 200 ms window) — the LED now falls back to blue breathing when no packets are live.

### Planned (next implementation phase)
- Multi-node unicast: send the same RTP stream to 2+ board IPs (P9).
- Failover → AP path exercise on hardware (bad SSID in NVS → 30 s → AP, NVS kept).

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
