# PROJECT STATE — LIVE STATUS (update after EVERY change, every compile, every flash, every test)

> **RULE: This file is always current.** Before any work: READ this file.
> After any work: UPDATE this file with micro-level detail (what changed, what worked, what failed, exact errors).
> Never re-try a failed approach without checking this file first. Never duplicate existing code — check here first.

---

## 1. WHERE WE ARE (current focus)
- Phase: **RTP/UDP product phase** — transitioning the verified TCP audio path to a product-grade WiFi speaker box
- Production build (verified flashing): DMA-backpressure pump, PSRAM ring buffer, ×2 gain, RGB LED VU/states, 2s boot tone
- Audio pipeline preserved, transport changed TCP → **RTP L16 over UDP** (48 kHz, 16-bit, mono, 20 ms frames, PT=96, seq+1/frame, ts+960/frame samples)
- **P1 RTP receiver now VERIFIED on hardware (2026-09-13)**: 30 s stream, 1272+ pkts, **dropped=0** — root cause of earlier silence was disabled IP reassembly (see §4)
- **P3 STA-from-NVS verified**: boots → cfg blob from NVS → joins <ssid> → GOT IP <board-ip>, no premature failover
- **P2 setup AP + captive portal VERIFIED on hardware (2026-09-13)**: empty-NVS boot → open AP `AudioNode-Setup` @192.168.4.1 → portal form → Save → NVS blob → reboot → STA from NVS (see §4 for the DHCPS boot-loop fix)
- **P4 factory reset VERIFIED on hardware (2026-09-14)**: BOOT held 5 s → NVS erased → reboot → `AudioNode-Setup` AP (exactly 1 cycle, no panic — the post-DHCPS-fix AP path was proven in the same run)
- **P4 → re-provision → STA → streaming round trip VERIFIED on hardware (2026-09-14)**: portal Save → NVS → reboot → STA (GOT IP <board-ip>) → 12 s RTP tone: 600 frames sent, board `pkts=503 dropped=0 pcm=965760 bytes` (503 × 1920 B byte-exact) with the source-IP whitelist enforced
- **Failover→AP path VERIFIED (2026-09-14)**: bad/typo'd SSID → association fails → no IP in 30 s → `failover: no IP in 30000 ms, opening setup AP (NVS kept)` → AP reopens by itself → portal recovery → STA + GOT IP
- **P5 LED regression FIXED + VERIFIED (2026-09-14)**: the LED used to freeze solid red after any stream (sticky `net_state`, frozen VU level). Streaming is now detected by packet recency → blue breathing ↔ VU ↔ blue
- Known pitfall: stale zombie senders/monitors poison tests — ALWAYS `taskkill /F /IM python.exe /T` + kill monitor wrappers, verify 0 pythons, before any run
- **Repo restructured (2026-09-15)**: `audio_node/` → `firmware/`, all root `*.md` → `docs/`, new `audio_player/` PC app (`server/send_pcm.py` → `audio_player/send_pcm.py`). Firmware rebuild from the new `firmware/` path **VERIFIED**: `Project build complete`, 0 errors, `firmware/build/audio_node.bin` (901,232 B)
- **audio_player V1 (browser app) VERIFIED on hardware (2026-09-15)**: Flask + Socket.IO (eventlet) + ffmpeg → RTP L16/UDP. 20 s stream: board `pkts=821 dropped=0`, `pcm = pkts × 1920` byte-exact, pkts deltas 250/250/251 per 5 s = **50 pkts/s (real time)**, position **1:1** with the wall clock, seek/volume/stop all correct. Full log: `logs/2026-09-15_app-v1-live.md`
- Four app bugs were found by these tests and fixed (all in §4): position-loop deadlock, RTP pacing free-run (3x real time → `dropped=45`), position lost on pipeline restart, natural EOF stuck "playing"
- **Tone-ladder diagnosis + retuned chain (2026-09-15 evening)**: 8-tone test through the real speaker → bass clean, **250 Hz–1 kHz distorts first**, 2k/4k cleanest; the song's sub-bass peaks at 41 Hz (unreproducible on a 3 W driver). ffmpeg chain now = 65 Hz highpass, −3 dB bass shelf @120 Hz, compressor, **alimiter @ 0.5** (with the board's ×2 gain, the DAC can never clip again at any UI volume). User: clearly better. Log: `logs/2026-09-15_tone-diagnosis.md`
- **10-band EQ + presets added to the app (2026-09-15 evening)**: VLC grid (60/170/310/600 Hz, 1/3/6/12/14/16 kHz), preamp ±12 dB, live apply (pipeline restarts at position), **limiter stays last**; built-ins: Flat, Acoustic, Bass Booster, Bass Reducer, Classical, Pop, Rock / Metal, Vocal / Voice, Treble Boost, Mid Cut (speaker); user presets persist to `audio_player/eq_presets.json` (git-ignored). REST: GET/POST `/api/eq`, POST `/api/eq/preset` (apply), POST `/api/eq/presets` (save). Selftest green + API smoke-tested; **not yet committed — waiting on the user's ears**
- Toolchain: **IDF v6.1** `D:\esp32\v6.1\esp-idf` + `C:\Espressif\...\env.ps1`

## 2. FEATURE MAP (what exists / what's left)
| Feature | Status | Where | Notes |
|---|---|---|---|
| Project scaffold (CMake, main, sdkconfig) | ✅ DONE | `firmware/` | esp32s3 target, builds with IDF v6.1, PSRAM octal enabled. **Rebuilt from `firmware/` after the restructure 2026-09-15: `Project build complete`, 0 errors** |
| M4: TCP 2-min acceptance (data path verified) | ✅ DONE (archived) | `main/main.c` | 2-min run 0 drops 0 errors, prompt stop — data path proven, protocol now superseded by RTP/UDP |
| **P1: RTP L16 over UDP receiver + validation** | ✅ VERIFIED 2026-09-13 | `main/main.c` | UDP recv 1234, RTP header validation (v=2, PT=96), source-IP whitelist, seq-gap silence-fill, 5 s stats. Required `CONFIG_LWIP_IP4_REASSEMBLY=y` (1932 B frames > MTU 1500 arrive fragmented). 30 s stream 1272+ pkts dropped=0 |
| **P2: Setup AP + captive portal** | ✅ VERIFIED 2026-09-13 | `main/main.c` | SoftAP `AudioNode-Setup` open AP @192.168.4.1, httpd `/` form + `/save` POST → NVS blob → reboot to STA. Empty NVS (first boot / factory reset) → setup AP. AP IP requires DHCPS stopped first, and the old factory WiFi seed is removed — see §4 |
| **P3: STA mode + WiFi failover** | ✅ VERIFIED 2026-09-13 | `main/main.c` | NVS cfg blob (SSID/pass/server ip:port) w/ first-boot factory seed; STA join verified (GOT IP, no failover). Failover task: no IP in 30 s → setup AP (NVS kept); wifi drop → auto-reconnect (NVS kept). Failover→AP VERIFIED 2026-09-14 (typo'd SSID → association failed → no IP in 30 s → AP reopened by itself, NVS kept → portal recovery → STA + GOT IP) |
| **P4: Factory reset (GPIO0)** | ✅ VERIFIED 2026-09-14 | `main/main.c` | BOOT button (GPIO0) held 5 s → `nvs_flash_erase()` → `esp_restart()` → setup AP. Short presses ignored. Erase failure aborts instead of rebooting (config kept, not lost). WiFi loss does NOT erase NVS |
| **P5: RGB LED states (setup/AP/waiting/streaming/VU)** | ✅ FIXED 2026-09-14 | `main/main.c` | red = wifi down / setup AP · blue breathing = got IP, no live stream · VU = streaming. Was stuck solid red after any stream (regression from the UDP rewrite — see §4); streaming is now derived from packet recency (200 ms) |
| **P6: PSRAM ring buffer (jitter cushion)** | ✅ DONE | `main/main.c` | Preserved; UDP-RX writes validated PCM, pump pulls — unchanged |
| **P7: DMA-backpressure pump** | ✅ DONE | `main/main.c` | Preserved; no fixed sleep — unchanged |
| **P8: RTP sender (Python, file/loop/tone)** | ✅ DONE+USED 2026-09-13 | `audio_player/send_pcm.py` | RTP UDP sender with tone/file/loop submodes; 30 s tone @50 fps delivered 1500 frames to board (P1 receive verified against it) |
| **A1: audio_player browser app (UI + REST + Socket.IO)** | ✅ VERIFIED 2026-09-15 | `audio_player/` | Flask + Flask-SocketIO (eventlet) + ffmpeg. Library picker w/ ffprobe durations, play/stop/seek/volume, 250 ms position push, per-node readout. `python -m audio_player.app` → http://localhost:5000 |
| **A2: RTP pipeline with real-time pacing** | ✅ VERIFIED 2026-09-15 | `audio_player/player.py` | One ffmpeg→RTP pipeline per stream; pacing anchored on the first frame → 50.0 pkts/s, board `dropped=0`. Absolute position across pipeline restarts (`_base_samples`) |
| **A3: selftest (no framework, 29 asserts)** | ✅ DONE 2026-09-15 | `audio_player/selftest.py` | `python -m audio_player.selftest`: RTP wire format, frame math, **real send rate over a loopback UDP socket** (pacing regression), position-across-restart, HTML↔JS id contract |
| **A4: repo restructure** | ✅ DONE 2026-09-15 | repo root | `firmware/` + `audio_player/` + `docs/`; stray root `main/`, `server/`, `build_html.py` deleted; `.gitignore` updated |
| **P9: Multi-node unicast** | 🚧 PARTIAL | `audio_player/` | `player._send_frame` already loops over `cfg.nodes`, and the app takes repeatable `--node IP:PORT`; needs an on-hardware 2-board test |
| **P10: Audio gain chain (amp quirk)** | ✅ DONE | `main/main.c` + sender | ×2 digital gain on board (SD pin=VDD → 3 dB amp min → +6 dB); sender headroom — unchanged |
| **P11: 10-band EQ + presets (server-side)** | 🟡 code-complete, awaiting user ears | `audio_player/config.py`, `player.py`, `app.py`, `static/` | VLC 10-band grid + preamp; live apply via restart-at-position; alimiter stays LAST (never clip); 10 built-in presets + user presets in `eq_presets.json` (git-ignored) |

## 3. VERIFIED WORKING ✅ (do not break)
**TCP prototype milestones — archived, audio pipeline reused in RTP build:**
- M0 1kHz serial tone via I2S (user verified by ear)
- M1 WiFi STA, power-save OFF (IP <board-ip>, RSSI -34..-41)
- M2 TCP client → PC server accept (port 1234)
- M3 streaming: 120.0 s / 11,520,000 bytes, 0 drops, 0 recv errors, prompt stop on stream end (user-confirmed, 2026-09-10)
- PSRAM octal ring buffer (65 KB) stable under 2-min continuous load
- DMA-backpressure pump (no fixed sleep — fixed sleep caused periodic glitches)
- ×2 digital gain (SD pin at VDD → amp's 3 dB min → +6 dB board gain, sender headroom)
- RGB LED: red/blue-breathing/VU, 2 s boot tone (user-confirmed working)
- Download-mode recovery: `esptool -p COM5 run` + `monitor --no-reset`

**RTP/UDP production phase — verified on hardware:**
- P1 RTP L16/UDP receive: 30 s stream, 1272+ pkts, dropped=0 (needs `CONFIG_LWIP_IP4_REASSEMBLY=y`)
- P2 setup AP + captive portal: empty NVS → `AudioNode-Setup` @192.168.4.1 → portal form → Save → NVS → reboot → STA
- P3 STA-from-NVS: boot → saved cfg → joins <ssid> → GOT IP <board-ip>
- P4 factory reset: BOOT held 5 s → NVS erased → `rst:0xc (RTC_SW_CPU_RST)` → `cfg: none in NVS` → softAP `AudioNode-Setup` + DHCPS 192.168.4.1 + portal, exactly 1 cycle, no panic. Side effect on the post-reset boot: `W (1036) phy_init: failed to load RF calibration data (0x1102), falling back to full calibration` — expected (calibration was wiped), self-healing
- P4 re-provision round trip: `cfg: saved via portal (SSID=<ssid> server=<pc-ip>:1234)` → reboot → `cfg: server whitelist <pc-ip>` → `STA: joining <ssid>` → `GOT IP: <board-ip>`. Followed by an RTP regression run: sender 600 frames / 12.0 s, board `pkts=503 dropped=0 pcm=965760 bytes` — P1 still good with the whitelist active
- P5 LED state machine fixed 2026-09-14: blue breathing (waiting) → VU while a stream plays → back to blue within ~200 ms after it stops (user-verified by eye). 60 s run: 3000 frames sent, `pkts=2753 dropped=1 pcm=5285760` byte-exact — the audio path was untouched and stayed healthy

**audio_player (PC server app) — verified on hardware 2026-09-15 (log: `logs/2026-09-15_app-v1-live.md`):**
- UI + REST all serve: `GET /` 200 (1881 B), `/static/app.js` 200, `/static/style.css` 200, `/api/library|play|stop|volume|seek|status` all answer
- 20 s stream to <board-ip>: `udp: pkts=70/320/570/821 dropped=0` → deltas 250/250/251 per 5 s = **50.0/50.0/50.2 pkts/s = real time**; `pcm == pkts × 1920` byte-exact; ring 4.8–10.4 KB; RSSI −44…−50 dBm
- Position 1:1 with the wall clock (35 s soak: 4.76→9.80→14.80→19.82→24.84→29.84→34.86 s; the ~0.25 s offset is ffmpeg spawn/decode)
- seek to 100 s → 101.36 s reported (absolute); volume 0.5→0.8 → position continued ~102.5 s (no restart at 0); stop → `stopped`, position 0
- `python -m audio_player.selftest` → **29/29 pass**, including the pacing regression test (50 frames/s measured on the wire)
- Firmware still builds from the restructured path: `cd firmware; idf.py build` → `Project build complete`, 0 errors, `audio_node.bin` 901,232 B

## 4. TRIED & FAILED ❌ (NEVER re-try these; check before any fix attempt)
- ❌ **(2026-09-13) UDP datagrams 1932 B with `CONFIG_LWIP_IP4_REASSEMBLY` disabled** — every RTP frame (1932 B > 1500 MTU) arrives IP-fragmented and lwIP silently drops it: recvfrom blocks forever, ping still works, reverse path (board→PC 2 B probe) works. Root cause of "RTP receiver never fires". FIX: `CONFIG_LWIP_IP4_REASSEMBLY=y` in sdkconfig.defaults. With default `IP_REASS_MAX_PBUFS=10` there was still ~5% seq-drop; 20 → dropped=0.
- ❌ **(2026-09-13) `esp_wifi_init()` before `nvs_flash_init()`** — boot loop: `W (915) wifi:osi_nvs_open fail ret=4353`, `ESP_ERR_NVS_NOT_INITIALIZED` panic via ESP_ERROR_CHECK in app_main. FIX: NVS init must run FIRST in app_main, before netif/wifi init.
- ❌ **(2026-09-13) failover task ms/µs unit mismatch** — compared µs against `STA_FAIL_TIMEOUT_MS/1000` (=30) → AP mode fired ~30 ms after STA start, even though STA connected at 1.3 s. FIX: keep everything in µs (`(int64_t)STA_FAIL_TIMEOUT_MS * 1000`).
- ❌ **(2026-09-13) `esp_netif_set_ip_info()` on the AP netif while its DHCPS is running** — panic `ESP_ERROR_CHECK failed: esp_err_t 0x5007 (ESP_ERR_ESP_NETIF_DHCP_NOT_STOPPED)` at `setup_ap_start` (main.c:322) → `abort()` → reboot → **setup-AP boot loop** (439 KB of repeated identical panics). The default AP netif already runs DHCPS bound to 192.168.4.1 and refuses an IP change while up. FIX: `esp_netif_dhcps_stop(ap_if)` → `esp_netif_set_ip_info()` → `esp_netif_dhcps_start(ap_if)`.
- ❌ **(2026-09-13) factory WiFi seed on empty NVS** — `cfg_factory_seed()` wrote lab WiFi (<ssid>/<password>) on first boot, so a fresh board auto-joined the lab instead of running `AudioNode-Setup`. Contradicted the documented spec ("first boot / factory reset → setup AP"). REMOVED: empty NVS now leaves a zeroed cfg → empty SSID → setup AP.
- ℹ️ **(2026-09-14) source-IP whitelist vs sender host** — the whitelist is honest, not sticky: the board accepted packets only from the IP the portal stored (`<pc-ip>`). This PC reaches the LAN over **Ethernet = <pc-ip>** (its Wi-Fi adapter is separate), so running `send_pcm.py` from this PC matches the stored whitelist. If the sender moves to another host, update the portal's Server IP (or set it to `0.0.0.0` to accept any).
- ❌ **(2026-09-14) RGB LED stuck solid red after any stream** — `udp_task` sets `net_state = 2` ("streaming") on every packet but **nothing clears it when the stream ends** (the old TCP task had that stream-end path; the UDP rewrite lost it). The pump's starved branch (`avail < 512 B` — the steady state once a stream stops) writes silence and then `continue`s, **skipping the VU-update block**, so `vu_level` froze at its last loud peak → the VU colour (loud = red) was displayed forever while WiFi was perfectly healthy (ping OK, `rssi` still printing, no disconnect entries). Root cause = sticky streaming flag. FIX: derive "streaming" from **packet recency** — `last_pkt_ms` stamped per accepted packet; the LED treats a >200 ms gap as no live stream and falls back to blue breathing (net_state >= 1).
- ❌ **(2026-09-15) app `player.py` — pacing guard `if 0 < ahead < 0.1: time.sleep(ahead)`** — the upper bound silently disables pacing the moment the sender runs >100 ms ahead, which is immediate because ffmpeg hands the pump 4 frames per read. The sender free-ran at ffmpeg's decode rate (~3× real time): position advanced ~3020 ms per 1000 ms of wall clock, board logged `pkts=358 dropped=45` (ring overflowing). FIX: anchor `_start_wall` on the **first sent frame** (ffmpeg spawn/decode latency must not count as a pacing deficit) and sleep the **whole** lead, capped per iteration: `if ahead > 0: time.sleep(ahead if ahead < 0.25 else 0.25)`. → 50.0 pkts/s, `dropped=0`.
- ❌ **(2026-09-15) app `app.py` — `threading.Lock` nested in `background_position_loop`** — the loop called `_node_status()` while already holding `status_lock`; `threading.Lock` is NOT reentrant, so it deadlocked on its first iteration **while holding the lock forever**, hanging `/api/status` (request never returned) and the position push. FIX: `_nodes_for(state, pos_s)` takes no locks; compute nodes outside the `with status_lock` block. Rule: never call a lock-taking helper from inside a lock.
- ❌ **(2026-09-15) app `player.py` — pipeline restart lost the position** — `seek()` and `set_volume()`→`play()` both zero `_bytes_sent`, so a seek reported 0:00 and a volume change restarted the song from the beginning. FIX: `_base_samples` (samples played before the current pipeline); `sample_position = _base_samples + _bytes_sent/2`; `seek()` rebases on the requested absolute position; `set_volume()` = `self.seek(self.sample_position)`.
- ❌ **(2026-09-15) app `player.py` — natural EOF left the player "playing"** — `_pump()` reported `stopped` on ffmpeg EOF but never cleared `_running`, so `sample_position` kept returning the last byte count and the UI stayed "playing" forever on a finished file. FIX: clear `_running`, `_kill_pipeline()`, then report `stopped` — byte-for-byte the same end state as a manual stop.
| Date | What we tried | Exact error/symptom | Why failed (root cause) | Outcome |
|---|---|---|---|---|
| — | — | — | — | — |

## 5. ERROR LOG (every compile/flash/runtime error, chronologically)
| # | Date | Error message (verbatim) | Context | Fix attempted | Result |
|---|---|---|---|---|---|
| 1 | 2026-09-08 | `idf.py` not recognized | export.bat with D:\esp32\v6.1 silently failed (EIM install, nonstandard layout) | Created canonical `env.ps1` mirroring official EIM PowerShell profile | ✅ works |
| 2 | 2026-09-08 | `TypeError: expected string or bytes-like object, got 'NoneType'` in idf_extensions.py | idf.py needs ESP_IDF_VERSION env | Added `ESP_IDF_VERSION=6.1`, `IDF_VERSION=6.1.0`, `IDF_COMPONENT_LOCAL_STORAGE_URL` to env.ps1 | ✅ works |
| 3 | 2026-09-08 | `ERROR: COM3 failed to connect` | `idf.py flash` without -p auto-picked COM3 (Intel AMT!) | Always pass `-p COM5` | ✅ works |
| 4 | 2026-09-08 | `Could not open COM5 ... PermissionError(13)` | stale monitor python process held port | Kill stray python processes before flash | ✅ works |
| 5 | 2026-09-08 | `task_wdt: IDLE0 not reset` + backtrace in pump loop | tone loop blocked forever in app_main then spun on CPU0 | Moved pump to dedicated task with `vTaskDelay(4ms)` rate-limit + error-checked writes + precomputed 48-sample sine table | ✅ monitor clean |
| 6 | 2026-09-08 | `implicit declaration of sinf` / `M_PI undeclared` | lost `#include <math.h>` when adding WiFi includes | Re-added include | ✅ |
| 7 | 2026-09-08 | `ninja: fatal: ReadFile: The handle is invalid.` | launching build detached via Start-Process broke stdio handles | Run builds synchronously in foreground | ✅ |
| 8 | 2026-09-08 | `WARNING: PSRAM alloc failed` | N8R2 octal PSRAM not enabled by default sdkconfig | Added `sdkconfig.defaults` (SPIRAM=y, MODE_OCT, 8MB flash); delete sdkconfig + set-target to regenerate | ✅ PSRAM alloc OK |
| 9 | 2026-09-08 | build targeted **esp32** (not s3!) | deleted sdkconfig but ran build without set-target | Always run set-target after deleting sdkconfig | ✅ |
| 10 | 2026-09-08 | PC `10054` + board `recv err errno=104 after 0 bytes` | ghost/stale connection from previous board boot accepted by fresh server (race: server started while board was mid-retry from dead session) | Board: 5s delay before first connect; harness: start monitor BEFORE server; kill orphan pythons between tests | ✅ full 30s stream clean |
| 11 | 2026-09-08 | zombie python processes survive test harness | Stop-Process kills wrapper pwsh, not python children | harness kills all python after test; kill pythons before each test | ✅ |
| 12 | 2026-09-10 | board stuck at `rst:0x15 USB_UART_CHIP_RESET, boot:0x0 DOWNLOAD` "waiting for download"; each `idf.py monitor` open re-reset it into download mode | USB-CDC boot-mode latch; unplug/replug normally fixes | With COM5 free: `python -m esptool --chip esp32s3 -p COM5 run` then `idf.py -p COM5 monitor --no-reset`. Harness runs esptool FIRST, then monitor (never concurrently — port conflict) | ✅ no unplug needed |
| 13 | 2026-09-13 | `ESP_ERROR_CHECK failed: esp_err_t 0x5007 (ESP_ERR_ESP_NETIF_DHCP_NOT_STOPPED)` | setup-AP boot loop: `esp_netif_set_ip_info()` called while the AP netif's DHCPS was running (`setup_ap_start`, main.c:322) → abort → reboot, forever | `esp_netif_dhcps_stop()` → `set_ip_info()` → `esp_netif_dhcps_start()` | ✅ AP up at 192.168.4.1 |
| 14 | 2026-09-15 | `GET /api/status` never returns (client timeout after 10 s), no error in the server log | app: `background_position_loop` called `_node_status()` while holding `status_lock` (non-reentrant) → self-deadlock on the first iteration | `_nodes_for(state, pos_s)` with no locks; call it outside the `with status_lock` block | ✅ 200 in 0 ms to 127.0.0.1 |
| 15 | 2026-09-15 | Position advanced ~3020 ms per 1000 ms of wall clock; board monitor `udp: pkts=358 dropped=45` | app `player.py` pacing `if 0 < ahead < 0.1` → the upper bound disabled pacing as soon as the sender was >100 ms ahead | Anchor `_start_wall` on the first frame; `if ahead > 0: time.sleep(min(ahead, 0.25))` | ✅ 50.0 pkts/s, `dropped=0` |
| 16 | 2026-09-15 | After `POST /api/seek {position_ms:100000}` status reported ~1500 ms instead of ~100000 ms | app `player.py`: `seek()` zeroed `_bytes_sent` and position was computed from it alone | `_base_samples` offset; `sample_position = _base_samples + _bytes_sent/2`; `seek()` rebases | ✅ reported 101360 ms |
| 17 | 2026-09-15 | Audio restarted from 0:00 on every volume change; finished file left the UI "playing" forever | app `player.py`: `set_volume()` did stop+play from position 0; `_pump()` never cleared `_running` on natural EOF | `set_volume()` → `self.seek(self.sample_position)`; `_pump()` clears `_running` + kills the pipeline before reporting `stopped` | ✅ volume keeps position; EOF behaves like stop |
| 18 | 2026-09-15 | `idf_monitor` attaches to COM5 but prints nothing while a stream is running | 6 orphaned `idf_monitor`/`esp_idf_monitor` python processes from earlier sessions held COM5; `Stop-Job` kills the wrapper pwsh, not the python grandchild | Kill by PID: `Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where ... | Stop-Process -Force` | ✅ serial log readable again |
| 19 | 2026-09-15 | Build log restarted mid-build (`[176/979]` → `[1/1088]`), twice | `Start-Job` a long build, then keep issuing shell commands — the tool closes the previous terminal per command, killing the job's process tree | Run long builds as the only command, or launch detached (`Start-Process pwsh -File tmp\build_fw.ps1 -WindowStyle Hidden`) | ✅ `Project build complete` |

## 6. DECISIONS & REASONS

| Decision | Reason |
|---|---|
| RTP L16 over UDP (product) | Low latency, no head-of-line blocking, works with many-to-one streaming. (Prototype used TCP because early tests showed ~25% UDP loss on AP; that was a network condition issue — RTP with sequence validation + silence-fill is the correct production approach.) |
| RTP timestamp in samples (not ms) | At 48 kHz, +960 per 20 ms frame. Unambiguous seq/ts correlation; easy gap detection. |
| Silence-fill on packet loss | UDP is unreliable; never block I2S waiting for a lost packet. Silence one frame is better than glitch/buzz/replay. |
| Validate every UDP datagram | Version=2, PT=96, length, source IP whitelist, seq/ts sanity. A single bad packet corrupts all following audio (the "noisy sound" bug). |
| Explicit I2S byte-order conversion | Don't blitcopy network bytes to I2S — convert to the peripheral's expected format. |
| Board is UDP listener (not sender) | Server is behind firewall with port rules; server initiates to known board IP. Simpler for many-to-one. |
| No MCLK | MAX98357A derives its own clock |
| Setup AP = open (no password) | Simpler for first-time setup; the web form handles the real auth. AP is short-lived and local. |
| Factory reset = GPIO0 hold ~5 s, NVS erase | Only explicit user action resets config. WiFi loss does NOT erase NVS — board just re-connects. No bricking from router changes. |
| Unicast for multi-node (v1) | One packet per board. Multicast (239.x) is future — AP/router multicast behavior varies, not worth v1 complexity. |
| Preserve TCP prototype in git | Proves audio hardware; pipeline reused. Transport layer replaced, not the whole codebase. |
| Server app = Flask + Socket.IO (eventlet), ffmpeg via imageio-ffmpeg | Smallest stack that gives a real browser UI + push updates with zero packaging: no build step, no bundled runtime, ffmpeg comes as a pip package. **Known ceiling**: `async_mode="eventlet"` is deprecated in Flask-SocketIO and is not monkey-patched here, so the 250 ms position loop runs as a plain OS thread and emits across threads. Upgrade path: `threading` async mode, or monkey-patch eventlet at process start. |
| One `Player` pipeline shared by the app and the CLI | The app must not grow a second sender implementation — `audio_player/player.py` is the only ffmpeg→RTP code path; `send_pcm.py` and the app both pace the same way. Wire-format drift is caught by `selftest.py`, not by two copies of the code. |
| `tmp/` for scratch, `logs/` for evidence, one file per purpose | Anti-duplication rule: `test_2.py`/`sender_v2.py` are banned. Variation happens through CLI arguments. |
| Position is server-side only (V1) | The firmware has no back-channel: the UI shows what the server has *sent*, not what the board has *played*. A node's jitter-buffer depth is only visible on its serial console. V2 option: a UDP status packet from the board every second. |

## 7. GIT / COMMIT POLICY
- Commit **only verified working states** (compiled + flashed + observed OK on hardware).
- Commit message format: `M<x>: <one-line what works> (verified on hardware)`.
- If a fix fails → do NOT commit → revert or try different approach → update §4/§5.

## 8. ACCEPTANCE CRITERIA (what "verified" means per milestone)

| Milestone | Verified only when |
|---|---|
| M0 serial tone | Continuous clean tone from speaker, ≥30 s, confirmed by PC mic |
| M1 WiFi | Monitor log: got IP + RSSI ≤ -40 dBm, stable ≥60 s |
| M2 TCP (archived) | PC sender accept() fires, board logs connected, ≥60 s idle |
| M3 streaming (archived) | Speaker plays PC audio in sync, no dropouts ≥2 min, prompt stop (<500 ms) on end |
| P1 RTP recv | UDP packets received, validated (v=2, PT=96), 20 ms frames into ring, silence-fill on loss, no I2S blocking |
| P2 Setup AP | Board AP visible (SSID `AudioNode-Setup`), captive portal page loads, config saved to NVS |
| P3 STA mode | Board joins WiFi, gets IP, LED turns blue (waiting), starts listening |
| P4 Factory reset | ✅ GPIO0 held 5 s → NVS erased → board reboots to setup AP (verified 2026-09-14) |
| P5 Multi-node | Same RTP stream to N board IPs, each plays independently |

## 9. SESSION PROTOCOL (before every flash/test)
- Detect COM port fresh every session — COM5 = board, COM3 = Intel AMT (never use).
- Build must succeed before flashing. Never flash a stale build.
- Save monitor output to `logs/<date>_<milestone>.md` before touching code.
- Toolchain: **IDF v6.1 at `D:\esp32\v6.1\esp-idf`**, tools at `C:\Espressif\tools` (switched from old D:\esp32-tools v5.3.2 install).

## 10. FILE HYGIENE
- **Repository layout (since 2026-09-15)**: `firmware/` = ESP32 code · `audio_player/` = PC app + CLI sender + selftest · `docs/` = all markdown · `logs/` = session evidence · `tmp/` = scratch (git-ignored). Nothing experimental may sit in `firmware/` or `audio_player/`.
- One canonical file per purpose — never duplicate scripts/tests under new names (send_pcm.py stays send_pcm.py; the app's sender is `player.py`).
- Experiments/scratch → `tmp/` (git-ignored, periodically deleted). Never in the code tree.
- Logs → `logs/`. Old/abandoned files get deleted, not renamed.
- Before creating any file: check §2 + existing tree; extend existing files instead of adding new ones.
- The one runnable check for the app: `python -m audio_player.selftest` (no test framework, no fixtures). Any change to RTP framing, pacing, or position math must keep it green.

## 11. NEXT STEPS (ordered)
1. ✅ P1 RTP UDP receiver — VERIFIED on HW (30 s stream, 1272+ pkts, dropped=0) after IP-reassembly fix
2. ✅ P3 STA-from-NVS — VERIFIED on HW (GOT IP, RSSI -43, listening :1234)
3. ✅ P2 on-HW verify — VERIFIED 2026-09-13 (empty NVS → `AudioNode-Setup` AP → portal → Save → NVS → reboot → STA, GOT IP)
4. ✅ P4 factory reset — VERIFIED 2026-09-14 (BOOT 5 s → NVS erase → setup AP, one clean cycle)
5. ✅ Re-provision round trip — VERIFIED 2026-09-14 (portal → NVS → STA at <board-ip> → 12 s RTP tone, dropped=0, whitelist enforced). Node is back online
6. ✅ Failover→AP path — VERIFIED 2026-09-14 (bad SSID → 30 s → AP reopened by itself, NVS kept, portal recovery)
7. ✅ P5 LED state fix — VERIFIED 2026-09-14 (blue breathing ↔ VU ↔ blue, no more stuck red)
8. ✅ Repo restructure + `audio_player` V1 — VERIFIED 2026-09-15 (`firmware/` builds clean; app streams 50.0 pkts/s with `dropped=0`, position 1:1). Log: `logs/2026-09-15_app-v1-live.md`
9. 🔲 **Listen + tune EQ** — play the MP3 from the UI, pick/tune a preset (250 Hz–1 kHz distorts first on this speaker; sliders + Save… in the EQ panel), then commit the EQ + retuned-chain milestone
10. 🔲 P9: multi-node unicast on hardware (2 boards, one stream; the app already loops over `cfg.nodes`)
11. 🔲 V2 candidates: node back-channel (board → server status packet), MP3/AAC RTP depacketizer on the board, playlist/next-track, `threading` async mode to drop the eventlet deprecation
12. 🔲 Commit each verified milestone only

## 12. DEV TOOLING (2026-09-11, non-firmware)
- Cline global tooling installed (details: `logs/2026-09-11_cline-global-tooling.md`): ponytail rule
  (`~/.cline/rules/ponytail.md`), graphify skill (`~/.cline/skills/graphify/`) + `pip install graphifyy`,
  OmniRoute v3.8.50 (`npm i -g omniroute`, dashboard :20128, `omniroute setup-cline` wired the Cline CLI).
- No firmware code touched; no git commit for this (machine-level config, lives outside repo).

## 13. DEBUG TOOLS AVAILABLE
- Monitor logs over USB CDC (`idf.py -p COM5 monitor --no-reset`)
- PC microphone (use to verify tone quality/noise — proven method, tone/noise ratio ~99x on previous test)
- Board quirks: USB CDC can die after flash → unplug/replug; "waiting for download" → unplug/replug USB
- **Cline tooling quirks (2026-09-14)**: `run_commands` shell-integration capture can fail ("Command completion could not be observed") although the command actually ran — workaround: redirect to a file (`cmd > tmp\x.txt 2>&1`) and read that file. Bounded background monitoring: `Start-Job { ... idf.py -p COM5 monitor *> logs\<file>.md }` then `Stop-Job`/`Remove-Job`, and always `taskkill /F /IM python.exe /T` afterwards (zombie monitors hold COM5).