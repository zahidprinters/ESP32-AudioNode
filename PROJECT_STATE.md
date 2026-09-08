# PROJECT STATE — LIVE STATUS (update after EVERY change, every compile, every flash, every test)

> **RULE: This file is always current.** Before any work: READ this file.
> After any work: UPDATE this file with micro-level detail (what changed, what worked, what failed, exact errors).
> Never re-try a failed approach without checking this file first. Never duplicate existing code — check here first.

---

## 1. WHERE WE ARE (current focus)
- Phase: **Not started** (workspace is clean, fresh start)
- Current task: none — awaiting first task
- Last action: created project state + workflow system files
- Next step: scaffold ESP-IDF project, then M0 serial tone test

## 2. FEATURE MAP (what exists / what's left)
| Feature | Status | Where | Notes |
|---|---|---|---|
| Project scaffold (CMake, main, sdkconfig) | ⬜ TODO | — | — |
| M0: Serial tone test (I2S direct, no network) | ⬜ TODO | — | first milestone — proves amp+I2S |
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
| — | — | — | — | — | — |

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
- Detect COM port fresh every session (Device Manager or `[System.IO.Ports.SerialPort]::GetPortNames()`) — it has changed before (seen COM3 and COM5). Never assume COM5.
- Build must succeed before flashing. Never flash a stale build.
- Save monitor output to `logs/<date>_<milestone>.md` before touching code.

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