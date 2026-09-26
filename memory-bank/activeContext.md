# Active Context

_Last updated: 2026-09-26 (project-wide documentation audit)_

## Current focus

**Nothing is in flight.** The system is feature-complete for its stated scope
and verified on hardware. The 2026-09-26 pass was documentation-only: every
document was re-checked against the source, and the drift that turned up was
fixed. Open items are packaging and product decisions, in [progress.md](progress.md).

Authoritative detail lives in [`docs/PROJECT_STATE.md`](../docs/PROJECT_STATE.md)
and [`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md). This file is the entry
point, not a duplicate of them.

## Recently changed

Latest commits on `main`:

- `229e456` — ui: app shell with a sidebar and a three-line hamburger (verified)
- `211483f` — ui: rebuild the interface on a design system, dark + light, accessible
- `5d72dfb` — docs: document every function, add a function map, fix a false claim
- `51219e7` — feat: verify dependencies on every start, guide and log first-run failures
- `eb51c81` — fix: make start_audioplayer.bat actually work — one-click start, clean stop

## Next steps

1. **Packaging / installer** — not started. This is the main remaining work.
2. Decide whether multi-board sync is ever wanted, or whether the honest
   "fan-out, not synchronised" statement is the final answer.
3. Add the remaining documentation once packaging decisions settle.

## Tried and failed

*(recorded from `docs/PROJECT_STATE.md` history — expand as new attempts fail)*

- **Treated the UI "playing" indicator as proof of audio.** It only means the
  server is sending. The board has no back-channel, so it cannot confirm sound.
  Any change that reuses that indicator as evidence of audio is wrong by design.
- **Letting the memory bank drift from the code.** `techContext.md` named the
  wrong ESP-IDF version, the wrong PSRAM size and — worst — told a future
  session to flash **COM3**, the Intel AMT port. Documents that are never
  re-verified become instructions to do the wrong thing. Re-check every fact
  against the source when editing, not against another document.

## Open questions
- [ ] Is an installer wanted, or is `start_audioplayer.bat` good enough?
- [ ] Should the setup AP and the normal firmware share one partition table?

## Active decisions
- **RTP L16 over raw PCM, no compression** — keeps latency low and the
  firmware simple; a compressed format would need a decoder on the ESP32.
- **Setup AP reuses stored-credentials-first logic** — BOOT-held factory reset
  erases NVS and returns to the AP; a Wi-Fi drop never erases NVS.
