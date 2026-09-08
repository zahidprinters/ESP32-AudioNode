# PROJECT STATE — LIVE STATUS (update after EVERY change, every compile, every flash, every test)

> **RULE: This file is always current.** Before any work: READ this file.
> After any work: UPDATE this file with micro-level detail (what changed, what worked, what failed, exact errors).
> Never re-try a failed approach without checking this file first. Never duplicate existing code — check here first.

---

## 1. WHERE WE ARE (current focus)
- Phase: **M0 serial tone test — running on board, awaiting audio verification**
- Current task: user confirms tone is audible/clean (ear + PC mic)
- Last action: fixed TWDT spin (rate-limited pump task + 48-sample sine table), built+flashed, monitor clean (no WDT, no write errors)
- Next step: on user confirmation → mark M0 ✅ → git commit → M1 WiFi
- Toolchain: **IDF v6.1** `D:\esp32\v6.1\esp-idf` + `C:\Espressif\tools` — NOTE: export.bat does NOT work (EIM install); use `D:\esp-idf\env.ps1` (canonical env script).

## 2. FEATURE MAP (what exists / what's left)
| Feature | Status | Where | Notes |
|---|---|---|---|
| Project scaffold (CMake, main, sdkconfig) | ✅ DONE | `audio_node/` | esp32s3 target, builds with IDF v6.1 |
| M0: Serial tone test (I2S direct, no network) | 🔨 ON BOARD — verifying | `audio_node/main/main.c` | 1kHz tone, pump task rate-limited |
| M1: WiFi connect (power-save OFF) | ⬜ TODO | — | — |
| M2: TCP client → PC server <pc-ip>:1234 | ⬜ TODO | — | board = client |
| M3: Raw PCM TCP stream playback + jitter buffer (PSRAM) | ⬜ TODO | — | 48k/16bit/MONO |
| PC-side test sender (Python, TCP) | ⬜ TODO | `server/` | — |
| Stream-end flush (audio stops promptly) | ⬜ TODO | — | — |

## 3. VERIFIED WORKING ✅ (do not break)
- (none yet — will be filled after M0 passes)

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

## 9. DEBUG TOOLS AVAILABLE
- Monitor logs over USB CDC (`idf.py -p COM5 monitor --no-reset`)
- PC microphone (use to verify tone quality/noise — proven method, tone/noise ratio ~99x on previous test)
- Board quirks: USB CDC can die after flash → unplug/replug; "waiting for download" → unplug/replug USB