# PROJECT STATE — LIVE STATUS (update after EVERY change, every compile, every flash, every test)

> **RULE: This file is always current.** Before any work: READ this file.
> After any work: UPDATE this file with micro-level detail (what changed, what worked, what failed, exact errors).
> Never re-try a failed approach without checking this file first. Never duplicate existing code — check here first.

---

## 1. WHERE WE ARE (current focus)
- Phase: **RTP/UDP product phase** — transitioning the verified TCP audio path to a product-grade WiFi speaker box
- Production build (verified flashing): DMA-backpressure pump, PSRAM ring buffer, ×2 gain, RGB LED VU/states, 2s boot tone
- Audio pipeline preserved, transport changing TCP → **RTP L16 over UDP** (48 kHz, 16-bit, mono, 20 ms frames, PT=96, seq+1/frame, ts+960/frame samples)
- New subsystems to build: setup AP + captive portal + NVS config, STA mode + WiFi failover, UDP RTP listener with packet validation, silence-fill on loss, factory reset (GPIO0 ~5 s hold)
- Known pitfall: stale zombie senders/monitors poison tests — ALWAYS `taskkill /F /IM python.exe /T` + kill monitor wrappers, verify 0 pythons, before any run
- Toolchain: **IDF v6.1** `D:\esp32\v6.1\esp-idf` + `C:\Espressif\...\env.ps1`

## 2. FEATURE MAP (what exists / what's left)
| Feature | Status | Where | Notes |
|---|---|---|---|
| Project scaffold (CMake, main, sdkconfig) | ✅ DONE | `audio_node/` | esp32s3 target, builds with IDF v6.1, PSRAM octal enabled |
| M4: TCP 2-min acceptance (data path verified) | ✅ DONE (archived) | `main/main.c` | 2-min run 0 drops 0 errors, prompt stop — data path proven, protocol now superseded by RTP/UDP |
| **P1: RTP L16 over UDP receiver + validation** | 🚧 DESIGN | `main/main.c` (new / transport) | UDP recv 1234, RTP header validation (v=2, PT=96, seq+ts), source-IP whitelist, silence-fill on loss. Never block I2S on missing UDP. |
| **P2: Setup AP + captive portal** | 🔲 TODO (next) | `main/main.c` | SoftAP `AudioNode-Setup`, HTTP server, config page (WiFi SSID/pw, server IP, port) |
| **P3: STA mode + WiFi failover** | 🔲 TODO | `main/main.c` | Connect to configured WiFi; on success start RTP listener; ~30 s failure → back to AP (keep NVS); WiFi drop → auto-reconnect (no erase) |
| **P4: Factory reset (GPIO0)** | 🔲 TODO (next) | `main/main.c` | BOOT button (GPIO0) held ~5 s → erase NVS → reboot to setup AP. Short presses ignored. WiFi loss does NOT erase NVS |
| **P5: RGB LED states (setup/AP/STAnstreaming/VU)** | ✅ DONE | `main/main.c` | Preserved from TCP build; red / blue breathing / VU, unchanged |
| **P6: PSRAM ring buffer (jitter cushion)** | ✅ DONE | `main/main.c` | Preserved; UDP-RX writes validated PCM, pump pulls — unchanged |
| **P7: DMA-backpressure pump** | ✅ DONE | `main/main.c` | Preserved; no fixed sleep — unchanged |
| **P8: RTP sender (Python, file/loop/tone)** | 🔲 TODO | `server/send_pcm.py` | Rewrite TCP sender to RTP UDP; file (ffmpeg), loop (WASAPI Win, future Mac/Linux), tone |
| **P9: Multi-node unicast** | 🔲 TODO (later) | `server/send_pcm.py` | Send same RTP stream to each board IP:port |
| **P10: Audio gain chain (amp quirk)** | ✅ DONE | `main/main.c` + sender | ×2 digital gain on board (SD pin=VDD → 3 dB amp min → +6 dB); sender headroom — unchanged |

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

**New production protocol:** None yet — entering RTP/UDP build phase.

## 4. TRIED & FAILED ❌ (NEVER re-try these; check before any fix attempt)
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
| P4 Factory reset | GPIO0 held 5 s → NVS erased → board reboots to setup AP |
| P5 Multi-node | Same RTP stream to N board IPs, each plays independently |

## 9. SESSION PROTOCOL (before every flash/test)
- Detect COM port fresh every session — COM5 = board, COM3 = Intel AMT (never use).
- Build must succeed before flashing. Never flash a stale build.
- Save monitor output to `logs/<date>_<milestone>.md` before touching code.
- Toolchain: **IDF v6.1 at `D:\esp32\v6.1\esp-idf`**, tools at `C:\Espressif\tools` (switched from old D:\esp32-tools v5.3.2 install).

## 10. FILE HYGIENE
- One canonical file per purpose — never duplicate scripts/tests under new names (send_pcm.py stays send_pcm.py).
- Experiments/scratch → `tmp/` (git-ignored, periodically deleted). Never in the code tree.
- Logs → `logs/`. Old/abandoned files get deleted, not renamed.
- Before creating any file: check §2 + existing tree; extend existing files instead of adding new ones.

## 11. NEXT STEPS (ordered)
1. ✅ Documentation: README.md, ARCHITECTURE.md, SERVER_SETUP.md, GUIDELINES.md, PROJECT_STATE updated for RTP/UDP product phase
2. 📝 P1: Implement RTP L16 UDP receiver + validation in `main/main.c` (reuse I2S/ring/pump/gain/LED)
3. 🔲 P2+P3: Setup AP + captive portal + NVS config + STA mode + WiFi failover in `main/main.c`
4. 🔲 P4: Factory reset (GPIO0 ~5 s hold) in `main/main.c`
5. 🔲 P8: Rewrite `server/send_pcm.py` → RTP UDP sender (file/loop/tone submodes)
6. 🔲 P5: Verify multi-node (send to 2+ board IPs)
7. 🔲 Build → flash → test each milestone → commit only if verified

## 12. DEV TOOLING (2026-09-11, non-firmware)
- Cline global tooling installed (details: `logs/2026-09-11_cline-global-tooling.md`): ponytail rule
  (`~/.cline/rules/ponytail.md`), graphify skill (`~/.cline/skills/graphify/`) + `pip install graphifyy`,
  OmniRoute v3.8.50 (`npm i -g omniroute`, dashboard :20128, `omniroute setup-cline` wired the Cline CLI).
- No firmware code touched; no git commit for this (machine-level config, lives outside repo).

## 9. DEBUG TOOLS AVAILABLE
- Monitor logs over USB CDC (`idf.py -p COM5 monitor --no-reset`)
- PC microphone (use to verify tone quality/noise — proven method, tone/noise ratio ~99x on previous test)
- Board quirks: USB CDC can die after flash → unplug/replug; "waiting for download" → unplug/replug USB