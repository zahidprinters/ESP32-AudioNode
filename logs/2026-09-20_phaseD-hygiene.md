# 2026-09-20 — Phase D: stream/timer/handle hygiene (#17/#10/#6/#28; #18 rejected) — P17

## What changed (`firmware/main/main.c` only — 4 hunks)
- **#17** silence fill on a seq gap is now capped by the ring's free space, read under
  `ring_mutex`: `if (gap > ring_free() / FRAME_BYTES) gap = ring_free() / FRAME_BYTES`.
  The 64-frame worst case (122 KB) could previously saturate the 256 KB ring so the REAL
  packet written on the next line got 0 bytes (`ring_write` returns partial when full —
  corruption was never possible; the cap removes the crowding-out). `dropped` still counts
  the true gap.
- **#10** `tone_ms` moved from a loop-local `static` to task scope (explicit init at task
  start); the stale "tcp_task switches back to mode 1" comment corrected — `udp_task` sets
  `play_mode = 1` on the first packet.
- **#6** failover: `if (ap_active) { sta_start = 0; continue; }` — the no-IP timer can
  never survive into a future STA attempt. Inert today (`ap_active` never returns to 0
  mid-boot; E-2).
- **#28** `setup_ap_start`: `hd` is static and `httpd_stop(hd)` runs before any restart;
  `hd = NULL` on `httpd_start` failure (previously the failure path could leave a stale
  handle). Inert today (single call).
- **#18 REJECTED** (no code change): see AUDIT.md E-15 — `int64_t last_pkt_ms` would
  introduce a torn-read race (udp_task writes, led_task reads; Xtensa 64-bit access is two
  halves) where the current `uint32_t` pattern is single-word atomic AND wrap-correct.

## Build + flash
- `idf.py build` → 0 errors (`audio_node.bin` 0xdc730, +496 over Phase C).
- flash: **Hash of data verified.**

## Gate A — 60 s stream
```
sender: done: 3000 frames (60.0s) in 60.0s          (50.0 fps)
board:  pkts=1558→1808→2059→2310→2561→2806  (+250..251 per 5.0 s = 50.0 pps)
        dropped=9→15   ring=44–47 KB (bounded)
final:  idle 30 s, pkts=2984 dropped=15 total=5729280   ← 2984 × 1920 = byte-exact
```
~0.5% air loss (RF calmed vs the 2–6% earlier today); ring never saturated.

## Gate B — mid-stream kill / restart
- sender1 killed at ~13.8 s (`sent 650 frames (13.0s)` last flushed line)
- 8 s gap (board drains ring → silence)
- sender2: `done: 750 frames (15.0s) in 15.0s`
- board during recovery: `pkts=944 (t=31104 ms) → 1194 (t=36104 ms)` = +250/5.0 s =
  **exactly 50 pps**, `dropped=3` total (the seq reset on restart costs ~1 drop by design:
  runaway-gap cap maps it to 1), ring 8–12 KB
- **zero** panic/watchdog/abort/rst markers in the entire capture
- Surgical kill by PID (Stop-Process -Id) — taskkill /IM python.exe would have killed the
  serial monitor too.

## Tooling forensics (recorded in E-15)
The gate-B capture's file tail showed a boot with no `rst:` banner. Diagnosis: killing the
monitor's python pulses DTR/RTS on port release and the capture script relaunches; the
attach reset can also fire mid-stream (the 12 s post-check's lifetime totals restarted at
440 mid-run for the same reason — 440 × 1920 still byte-exact, and the post-stream
heartbeat showed identical totals, i.e. no hidden reboot AFTER the stream). The board
itself never crashed in any Phase D capture.

## Gate honesty
- Verified: 60 s byte-exact + ring bounded; kill/restart recovery at 50 pps; no crash.
- **Failover→AP re-verify deferred**: triggering failover requires provisioning a bad SSID
  through the portal — the Wi-Fi password is user-held. #6 is inert today (E-2) and the
  failover path itself was hardware-verified 2026-09-14 (P6). Offer of an assisted demo:
  provision a throwaway SSID → observe 30 s failover → re-provision (PC Wi-Fi can be the
  portal client now).
