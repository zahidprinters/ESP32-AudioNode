# 2026-09-20 — Phase F: polish (#8/#25), #20 stays deferred — P19 — AUDIT CLOSED

## What changed (`firmware/main/main.c` — 4 hunks, all cosmetic/documentation)
- **#8**: the Xtensa atomicity assumption is now written down at both flag clusters —
  the ring globals (`ring_head/tail`, `play_mode`, `pump_chunks`) and the LED flags
  (`net_state`, `last_pkt_ms`, `vu_level`): aligned 32-bit (or narrower) load/store is
  single-word atomic on ESP32-S3; `_Atomic` or a critical section is required if the code
  is ever ported off Xtensa; 64-bit handoffs would already be unsafe (the #18 corollary,
  E-15). No code change.
- **#25**: both UDP log lines (in-stream stats + idle heartbeat) now use `PRIu32`/`PRIu64`
  from `<inttypes.h>`; the `(unsigned long)`/`(unsigned long long)` casts are gone.
- **#20 stays deferred** — no measurement justifies rewriting the timing-critical ring
  path (ring steady at 8–47 KB across every session, 50 pps, zero stalls).

## Build + flash + gate
- `idf.py build` → 0 errors, binary unchanged (`0xdc750` — #8 is comment-only).
- flash: **Hash of data verified.**
- Hardware: 15 s stream → heartbeat printed with the new format specifiers and sane
  numbers: `udp: idle 30 s, pkts=721 dropped=19 total=1384320` = **721 × 1920 byte-exact**
  — both `PRIu32` and `PRIu64` verified live (no format garbage).

## Final audit accounting (`docs/AUDIT.md`)
**24 done · 5 not defects · 3 rejected/deferred (#20, #30, #18) · 0 open.**
Remaining optional items (no phase): the bad-IP → HTTP 400 wire test (next natural portal
session), an optional live failover demo, and #20 only if a future measurement justifies it.
