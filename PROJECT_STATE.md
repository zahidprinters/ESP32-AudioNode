# PROJECT STATE — LIVE STATUS (update after EVERY change, every compile, every flash, every test)

> **RULE: This file is always current.** Before any work: READ this file.
> After any work: UPDATE this file with micro-level detail (what changed, what worked, what failed, exact errors).
> Never re-try a failed approach without checking this file first. Never duplicate existing code — check here first.

---

## 1. WHERE WE ARE (current focus)
- Phase: **M4: MP3 streaming + RGB LED (VU + connection states) working — user-verified**
- Working build: pump pacing 4ms (DMA backpressure), PCM_GAIN x2 + sender headroom 0.45, highpass 120Hz, 2s power-on tone, RGB LED VU/state
- Tried & failed: PCM_GAIN x4 (clipping), acompressor/alimiter filter chain (sender slower than real-time → periodic underruns "long tones") — both reverted
- Next step: further robustness (WiFi drop resilience, reconnect mid-song) or features user requests
- Log: `logs/2026-09-10_M4-mp3-streaming.md`
- Toolchain: **IDF v6.1** `D:\esp32\v6.1\esp-idf` + `C:\Espressif\tools` — export.bat does NOT work (EIM install); use `D:\esp-idf\env.ps1`.

## 2. FEATURE MAP (what exists / what's left)
| Feature | Status | Where | Notes |
|---|---|---|---|
| Project scaffold (CMake, main, sdkconfig) | ✅ DONE | `audio_node/` | esp32s3 target, builds with IDF v6.1, PSRAM octal enabled |
| M0: Serial tone test (I2S direct, no network) | ✅ DONE | `main/main.c` | 1kHz tone clean (user verified by ear) |
| M1: WiFi connect (power-save OFF) | ✅ DONE | `main/main.c` | IP <board-ip>, RSSI -34..-38, stable 65s |
| M2: TCP client → PC server | ✅ DONE | `main/main.c` + `server/send_pcm.py` | accept + connection held (verified both sides) |
| M3: Raw PCM TCP stream + PSRAM jitter buffer | ✅ DONE | `main/main.c` | 2-min run: 11,520,000 B / 120.0 s, 0 drops 0 errors; audio user-confirmed, prompt stop |
| PC-side test sender (Python, TCP) | ✅ DONE | `server/send_pcm.py` | server + stream modes, CLI-arg variation |
| Stream-end flush (audio stops promptly) | ✅ DONE | `main/main.c` | ring_flush() on recv()==0; user-confirmed prompt stop |

## 3. VERIFIED WORKING ✅ (do not break)
- M0 1kHz serial tone via I2S (user verified by ear)
- M1 WiFi STA, power-save OFF (IP <board-ip>, RSSI -34..-41)
- M2 TCP client → PC server accept (port 1234)
- M3 streaming: 120.0 s / 11,520,000 bytes, 0 drops, 0 recv errors, prompt stop on stream end (user-confirmed, 2026-09-10)
- PSRAM octal ring buffer (256KB) stable under 2-min continuous load
- Download-mode recovery: `esptool -p COM5 run` + `monitor --no-reset` (see §5 #12)

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
| TCP not UDP | UDP lost ~25% packets on AP `<ssid>` |
| No MCLK | MAX98357A derives its own clock |
| Board = TCP client | PC behind firewall has rules for port 1234; board connects TO PC |

## 7. GIT / COMMIT POLICY
- Commit **only verified working states** (compiled + flashed + observed OK on hardware).
- Commit message format: `M<x>: <one-line what works> (verified on hardware)`.
- If a fix fails → do NOT commit → revert or try different approach → update §4/§5.

## 8. ACCEPTANCE CRITERIA (what "verified" means per milestone — objective, no guessing)
| Milestone | Verified only when |
|---|---|
| M0 serial tone | Continuous clean tone from speaker, confirmed by PC mic recording (no noise bursts, no dropouts for ≥30s) |
| M1 WiFi | Monitor log shows got IP + RSSI ≤ -40 dBm, connection stable ≥60s |
| M2 TCP | PC sender accept() fires, board logs connection established, survives ≥60s idle |
| M3 streaming | Speaker plays PC audio in sync, no dropouts ≥2min, stops promptly (<500ms) on stream end |

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
1. Scaffold project (set-target esp32s3)
2. M0 serial tone → verify by mic/ear
3. M1 WiFi connect → verify IP + RSSI in monitor log
4. M2 TCP connect → verify accept() on PC
5. M3 streaming → verify audio, log packet stats

## 12. DEV TOOLING (2026-09-11, non-firmware)
- Cline global tooling installed (details: `logs/2026-09-11_cline-global-tooling.md`): ponytail rule
  (`~/.cline/rules/ponytail.md`), graphify skill (`~/.cline/skills/graphify/`) + `pip install graphifyy`,
  OmniRoute v3.8.50 (`npm i -g omniroute`, dashboard :20128, `omniroute setup-cline` wired the Cline CLI).
- No firmware code touched; no git commit for this (machine-level config, lives outside repo).

## 9. DEBUG TOOLS AVAILABLE
- Monitor logs over USB CDC (`idf.py -p COM5 monitor --no-reset`)
- PC microphone (use to verify tone quality/noise — proven method, tone/noise ratio ~99x on previous test)
- Board quirks: USB CDC can die after flash → unplug/replug; "waiting for download" → unplug/replug USB