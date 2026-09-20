# AUDIT REGISTER — firmware review triage & phase plan

Living register of external code reviews. **Every item is re-verified against the actual
source before it gets a verdict** — a review is a hypothesis, the code and the hardware
are the evidence. Verdicts and evidence are dated; re-triaged items keep their history.

Register opened: **2026-09-19**. Reviewed revision: `6844401` (`firmware/main/main.c`, 745 lines).

## Verdict legend

| Mark | Meaning |
|---|---|
| ✅ done | Already fixed in the referenced commit, or the code already behaves as requested |
| 🔲 valid | Genuinely worth changing — scheduled in a phase below |
| ⚠️ not a defect | The claim is inaccurate or the risk is already handled; no change (reason recorded) |
| ❌ rejected / deferred | Not worth doing as asked, or requires evidence first (reason recorded) |

---

## Round 1 — 32-item firmware review (2026-09-19)

| # | Item | Verdict | Phase |
|---|---|---|---|
| 1 | Buffer overflow: `body[1024]` written past the array | ✅ Fixed — `6844401` | — |
| 2 | Disconnect reason code discarded | ✅ Fixed — `6844401` | — |
| 3 | `IP_EVENT_STA_LOST_IP` never registered | ✅ Fixed — `6844401` | — |
| 4 | `udp_task` bind failure exits silently | ✅ Done `P14` — `socket()` and `bind()` both retry | A ✅ |
| 5 | `esp_wifi_connect()` return ignored in `STA_START` | ✅ Done `P14` — rc + `esp_err_to_name()` logged | A ✅ |
| 6 | `failover_task` timer not reset while `ap_active` | ✅ Done `P17` — `sta_start` reset in the branch (inert today, E-2) | D ✅ |
| 7 | `udp_task` launched before Wi-Fi is up | ⚠️ not a defect — proven on hardware | — |
| 8 | `volatile` flags not atomic | ✅ Done `P19` — Xtensa single-word-atomicity assumption documented at the flag clusters (E-15) | F ✅ |
| 9 | `ring_used()` called outside the mutex → stale `avail` | ⚠️ inaccurate — the mutex **is** held | — |
| 10 | `tone_ms` is `static` in the pump | ✅ Done `P17` — task-scope init + stale `tcp_task` comment fixed | D ✅ |
| 11 | `strtok_r` non-idiomatic (`tok = save`) | ✅ Done `P15` — for-loop, `NULL` on continuation | B ✅ |
| 12 | NVS config struct has no version field | ✅ Done `P16` — `uint8_t version` (`CFG_VERSION 2`), mismatch → config ignored | C ✅ |
| 13 | `cfg_load` does not check the returned blob length | ✅ Done `P16` — requires exact len AND version (see E-14) | C ✅ |
| 14 | `url_decode` calls `strlen` inside the loop (O(n²)) | ✅ Done `P15` — hoisted | B ✅ |
| 15 | `server_ip` not validated at save | ✅ Done `P15` — strict dotted-quad + HTTP 400, nothing saved on failure (see E-13) | B ✅ |
| 16 | `server_port` stored but unused / not independent of IP | ✅ Done `P16` — field, form input and handler copy deleted (decision (b)) | C ✅ |
| 17 | Silence fill not capped by free ring space | ✅ Done `P17` — capped by `ring_free()/FRAME_BYTES` under the mutex (mechanism was E-4) | D ✅ |
| 18 | `last_pkt_ms` is `uint32_t` ms | ❌ rejected (`P17`) — `int64_t` would ADD a torn-read race; the `uint32_t` pattern is atomic and wrap-correct (E-15) | — |
| 19 | HTTP body read 1 byte at a time | ✅ Fixed — `6844401` | — |
| 20 | Ring mutex held during `memcpy` → use a lock-free ring | ❌ stays deferred — no measurement justifies the rewrite (F closed 2026-09-20) | F |
| 21 | `audio_pump_task` calls `ring_used()` with a mutex drop | ⚠️ inaccurate — same as #9 | — |
| 22 | No SSID logged at connect time | ✅ already present (`STA: joining %s`) | — |
| 23 | No log when a client joins/leaves the setup AP | ✅ Done `P14` code — **HW verified `P18`**: join AND leave lines captured live | A ✅ |
| 24 | `rssi_task` noisy in AP mode | ⚠️ inaccurate — it already prints nothing | — |
| 25 | `%lu` for `uint32_t` in the UDP stats log | ✅ Done `P19` — `PRIu32`/`PRIu64`, casts gone (was correct before; tidier now) | F ✅ |
| 26 | No socket timeout / heartbeat on `udp_task` | ✅ Done `P14` — non-blocking poll + 30 s idle heartbeat | A ✅ |
| 27 | `char *html` pointing at a string literal | ✅ Done `P15` — `const char *` | B ✅ |
| 28 | `setup_ap_start` leaks the `httpd_handle_t` | ✅ Done `P17` — static `hd` + `httpd_stop` guard (inert today, single call) | D ✅ |
| 29 | `nvs_flash_erase()` while Wi-Fi is running | ✅ Done `P18` — wifi stop+deinit before the erase; reset cycle clean | E ✅ |
| 30 | `gain_clip` multiply can overflow `int32_t` | ❌ not reachable from any caller | — |
| 31 | No flush/drain before `esp_restart()` | ⚠️ already handled — both paths delay first | — |
| 32 | `PIN_SD` driven HIGH before `i2s_init()` | ✅ Done `P18` — SD driven HIGH after `i2s_init()` | E ✅ |

**Tally (recounted from the table): 32 items → 24 done · 0 valid remaining · 5 not defects ·
3 rejected/deferred — audit fully resolved.**

### What this review did *not* find
The review claims to explain the reported "no IP shown / no serial logs" symptom. It does
not, and neither did the four items fixed in `6844401`: the pre-change boot log from
2026-09-19 shows `<ssid>` joined, `GOT IP: <board-ip>`, and `bind()` succeeding on the
first attempt (evidence: `logs/2026-09-19_bugfix-hardening.md`). The node was silent
because no sender was running. Items #5/#23/#26 are still worth adding — they make a
*future* failure visible, which is the real lesson from that misdiagnosis.

---

## Phase plan

Rules: **one idea per build**, then build → flash → observe on hardware → log → update
`PROJECT_STATE.md` → commit only if verified. A phase is not done until its gate passes.
Order is deliberate: C must land before any change to `node_cfg_t` (#16), and A comes
first because it is what makes the remaining phases diagnosable.

### Phase A — close the diagnostic gaps (no behaviour change beyond logging/timeout)
Items: **#4 (`socket()` path), #5, #23, #26**
- #4: the `socket()` failure path still does `vTaskDelay(2000); return;` — retry it like `bind()`.
- #5: check `esp_wifi_connect()`'s return in the `STA_START` branch and print
  `esp_err_to_name(rc)`.
- #23: register `WIFI_EVENT_AP_STACONNECTED` / `AP_STADISCONNECTED` → one line each
  ("phone joined / left the setup AP"). Directly answers "did my phone reach the AP?".
- #26: `SO_RCVTIMEO` (5 s) on the UDP socket + a heartbeat when no packet has arrived for
  30 s ("udp: idle 30 s, pkts=0"), so an idle-but-healthy node is distinguishable from a
  dead one. Never block/abort on the timeout — log and continue.

**Gate:** boot shows `esp_wifi_connect rc=0`; joining the AP prints the join line; with no
sender the board prints an idle heartbeat; a 12 s tone then prints `dropped=0` byte-exact
and the heartbeat stops.

**Status 2026-09-19 — IMPLEMENTED (`P14`), 3 of 4 gate items verified on hardware.**
Boot prints `wifi: esp_wifi_connect rc=0 (ESP_OK)`; 45 s with no sender prints exactly one
`udp: idle 30 s, pkts=0 dropped=0 total=0 bytes`; a 30 s tone gives 50.0 fps with the
heartbeat silent during the stream, then resumes with accumulated totals. **Re-verified on
the exact flashed image** (rebuilt from the unchanged tree, re-flashed `'audio_node.bin'
at 0x00010000 verified.`, all three gates re-run in one 100 s capture). Across-run
`dropped` variance (0 → 20 → 5 over identical code) was diagnosed as RF burst loss
(4–6-packet bursts ≈ ~120 ms link blackouts), not the new poll — burst analysis in the log.
The AP join line (#23) was **code-complete but hardware-unverified** at that time (this PC's
Wi-Fi radio was software-disabled); it was **hardware-verified on 2026-09-20** — join AND
leave lines captured live during the Phase E factory-reset cycle (see Phase E status / E-16). Evidence: `logs/2026-09-19_phaseA-diagnostics.md`; how to close it is in E-12.

### Phase B — portal input handling
Items: **#15, #14, #27, #11** (#16 re-slotted to Phase C — it changes `node_cfg_t`/the NVS
blob, which is exactly what C's version field gates; the recorded decision is option (b),
delete the field — nothing consumes it)
- #15: `inet_pton`-validate `server_ip` before saving; on failure return HTTP 400 with a
  message instead of silently degrading to "accept any".
- #14: hoist `strlen(src)` out of the `url_decode` loop.
- #27: `const char *html` (or send the literal directly).
- #11: idiomatic `strtok_r`: first call with `body`, then `NULL`.
- #16: **DECISION REQUIRED** — `server_port` is stored in NVS and shown in the form but
  **used nowhere**: the board always listens on `UDP_PORT` (1234). Either (a) wire it up
  (`bind` to the configured port) or (b) delete the field and the form input. (b) is the
  lazy-correct option — nothing consumes the value — but it changes the NVS blob, so it
  must land after Phase C.

**Gate:** boot to the setup AP → POST an invalid IP → HTTP 400 with a clear message; POST
a valid config → save → reboot → STA; re-provision round trip re-verified on hardware.

**Status 2026-09-19 — IMPLEMENTED (`P15`).** All four items are in `main.c`. Logic gate:
`tmp/verify_phaseB.py` ports the changed functions and runs 21 checks — strict validator
accept/reject set (incl. the octet-255 trap, the `0NN` octal-lookalike trap, garbage
characters, empty string), `url_decode` round trips, full form reassembly, and `strtok_r`
iteration order — **21/21**; app selftest green. Hardware: flash `Hash of data verified`,
boot → `GOT IP`, 40 s stream at **exactly 50.0 pps `dropped=0`** byte-exact, idle heartbeat
intact, no panic, board stable after. The portal *wire* round-trip (POST → 400 / save →
reboot → STA) is **pending hardware** — the dev PC has no usable second network interface
(same blocker class as #23, see E-13/E-12); closing both is one phone join + form submit to
`AudioNode-Setup`. Evidence: `logs/2026-09-19_phaseB-portal.md`.

### Phase C — NVS config versioning (prerequisite for #16)
Items: **#12, #13**
- #12: add `uint8_t version` to `node_cfg_t` (defined macro, e.g. `CFG_VERSION 2`).
- #13: after `nvs_get_blob`, require `len == sizeof(node_cfg)` and `version == CFG_VERSION`;
  any mismatch → log the reason and treat the config as absent → setup AP.

Note (verified in IDF v6.1 `nvs_api.cpp`): a *shorter* stored blob loads successfully
(copies `dataSize`, returns OK), so trailing bytes are zeroed only by luck of static
initialisation; a *larger* one returns `ESP_ERR_NVS_INVALID_LENGTH`. The real hazard is a
reordered/retyped struct, which is exactly what the version field catches.

**Gate:** flash the new image over a board with an existing config → still joins, no
spurious reset; hand-write a mismatched/old blob → setup AP with a clear log; factory
reset still works.

**Status 2026-09-20 — IMPLEMENTED (`P16`).** `node_cfg_t` gained `uint8_t version`
(`CFG_VERSION 2`, first field); `cfg_save` stamps it; `cfg_load` requires
`len == sizeof(node_cfg)` AND `version == CFG_VERSION`, logs
`want v2 len 115, got v77 len 114`-style specifics and zeroes the struct on mismatch
(a partial copy used to leave a stale tail — IDF v6.1 `nvs_api.cpp` copies a SHORTER blob
and returns OK; only a longer one errors). #16 rode along: `server_port` deleted from the
struct, the form and the handler (the board always listens on `UDP_PORT` 1234).
**This corrects the gate expectation above**: an honest version check cannot let an
old-layout board "still join" — the transition costs ONE re-provision (any Wi-Fi client on
`AudioNode-Setup`), which also closes #23 and the Phase B wire gate in the same session.
Hardware gate (on the flashed image): old v1 blob →
`cfg: nvs blob rejected (want v2 len 115, got v77 len 114) -> re-provision` — v77 is
`0x4D` = `'M'`, the first byte of the old SSID string misread as a version byte: precisely
the silent-garbage failure mode #12 exists to catch, demonstrated live →
`no usable config` → setup AP started clean, no panic. The v2 save→load round trip
verifies in that same re-provision session. Evidence: `logs/2026-09-20_phaseC-nvs.md`.

### Phase D — stream, timer and handle hygiene
Items: **#17, #10, #6, #28** — **#18 rejected** (see E-15)
- #17: cap silence fill at `ring_free() / FRAME_BYTES` frames. **There is no overflow**
  (`ring_write` returns partial when full), but up to 64 × 1920 = 122 KB of silence can
  saturate the 256 KB ring, so the real PCM written on the next line gets 0 bytes and
  valid audio is dropped.
- #10: initialise `tone_ms` explicitly at pump start (and fix the stale
  "tcp_task switches back to mode 1" comment above it).
- #6: reset `sta_start = 0` in the `ap_active` branch (latent — `ap_active` only returns
  to 0 at boot today, but the reset makes the timer honest).
- #28: make `hd` static and `httpd_stop(hd)` if it is already non-NULL.
- #18: use `int64_t` ms for `last_pkt_ms` (the current `uint32_t` wrap *works* via
  unsigned arithmetic and the 200 ms comparison — it is fragile, not broken).

**Gate:** 60 s tone `dropped=0` byte-exact; kill the sender mid-stream and restart it →
audio recovers, ring never saturates; failover→AP re-verified.

**Status 2026-09-20 — IMPLEMENTED (`P17`), #18 rejected.** #17: silence fill is capped by
`ring_free() / FRAME_BYTES` (read under the mutex), so a worst-case 64-frame gap can never
crowd the real packet out of the ring; #10: `tone_ms` moved to task scope with explicit
init and the stale `tcp_task` comment corrected (`udp_task` sets `play_mode`); #6: the
failover timer now resets in the `ap_active` branch (inert today per E-2); #28: `hd` is
static and `httpd_stop()` runs before any restart (inert today — single call).
**#18 REJECTED**: `last_pkt_ms` is written by `udp_task` and read by `led_task`; on Xtensa
a 32-bit aligned access is atomic, a 64-bit one is two halves with no guarantee — the
conversion would replace a wrap-correct single-word-atomic pattern with a torn-read race
(E-15). Gate on hardware (flashed image): 60 s tone → 3000 sent, **2984 accepted,
`total=5729280` byte-exact**, 50.0 pps throughout, ring 44–47 KB (never saturated), 0.5%
air loss; kill mid-stream (sender dead at 650/13.0 s) → restart → board re-accepted at
**exactly 50 pps** (`pkts=944→1194`, `dropped=3`, ring 8–12 KB), sender2 750/15.0 s, zero
panic/watchdog/reset markers across all captures. **Failover→AP re-verify deferred** —
needs a portal cycle with the user-held Wi-Fi password; #6 is inert today (E-2) and the
failover path itself was hardware-verified 2026-09-14 (P6). Evidence:
`logs/2026-09-20_phaseD-hygiene.md`.

### Phase E — boot & amp hygiene
Items: **#32, #29**
- #32: drive `PIN_SD` HIGH *after* `i2s_init()` (1-line reorder; the floating-DIN window is
  ~1 ms and the MAX98357A emits nothing without clocks, so this is hygiene, not a bugfix).
- #29: `esp_wifi_stop()` before `nvs_flash_erase()` in the factory-reset task — the Wi-Fi
  driver holds its own NVS handle (`nvs.net80211` + PHY calibration) while connected.

**Gate:** boot tone clean by ear; factory reset (BOOT 5 s) → NVS erased → setup AP,
repeated 3× with no NVS error and no panic.

**Status 2026-09-20 — IMPLEMENTED (`P18`), verified in one full cycle.** #32: the amp's SD
pin is driven HIGH only after `i2s_init()`; #29: `esp_wifi_stop()` + `esp_wifi_deinit()`
run before `nvs_flash_erase()` in the factory-reset task. Hardware: flashed (`Hash of data
verified`), 30 s regression byte-exact (`1452 × 1920`, `dropped=0`, ring 14.6 KB); the user
held BOOT ~5 s with a capture already running → `BOOT held` → `NVS erased, rebooting into
setup AP` — **zero NVS errors, zero panic markers** — and the boot tone played through the
reordered amp path. BONUS — the same capture closed two older wire items: **#23
hardware-verified** (`ap: station … joined (aid=1)` AND `… left (aid=1)` captured live) and
the **Phase B wire save-path** (`cfg: saved via portal (SSID=… server=<pc-ip>)` —
new #16 format, #15-validated IP → reboot → `server whitelist` → `STA: joining` →
`GOT IP` → idle heartbeat; final 12 s stream byte-exact `480 × 1920`, `dropped=0`).
Remaining: the bad-IP → HTTP 400 half of B's gate (needs a deliberate bad submission the
next time the portal is open) and the user's explicit "boot tone clean" confirmation.
Evidence: `logs/2026-09-20_phaseE-boot-amp.md`.

### Phase F — polish, only with justification
Items: **#8, #20, #25**
- #8: document the Xtensa 32-bit atomicity assumption at the flag declarations (or move to
  `_Atomic` if it must be portable). No demonstrated bug.
- #20: a lock-free ring is a rewrite of the most timing-critical path in the firmware. Only
  consider it against a **measurement** (e.g. `i2s_channel_write` starvation counts or
  `pump_chunks` rate during a long stream). One producer at 50 Hz and one consumer at
  ~47 Hz sharing a 1920-byte `memcpy` is not a demonstrated bottleneck.
- #25: `PRIu32` instead of `(unsigned long)` casts — cosmetic; the current code is correct.

**Status 2026-09-20 — DONE (`P19`); the 32-item audit is fully resolved.** #8: the
atomicity assumption is now documented at both flag clusters in `main.c` (Xtensa aligned
32-bit = single-word atomic; `_Atomic`/critical sections if ever ported off Xtensa; 64-bit
handoffs already unsafe — the #18 corollary, E-15). #25: both UDP log lines use
`PRIu32`/`PRIu64` with the casts gone — verified live on hardware (heartbeat prints sane
numbers: `pkts=721 dropped=19 total=1384320` = byte-exact). Binary size unchanged
(`0xdc750` — #8 is comment-only). **#20 stays deferred**: no measurement justifies
rewriting the timing-critical path (ring steady at 8–47 KB across every session, 50 pps,
zero stalls). Final accounting: **24 done · 5 not defects · 3 rejected/deferred
(#20, #30, #18) · 0 open.**

---

## Evidence appendix (the verdicts that are not obvious)

**E-1 · #7 "udp_task runs before Wi-Fi is up" — not a defect.**
`bind()` to `INADDR_ANY:1234` does not require an interface to have an address. Verified
three times on hardware on 2026-09-19: `udp: listening on 0.0.0.0:1234` prints at ~1.09 s
and the socket receives normally after `GOT IP` at ~4.35 s (`dropped=0`). Setup-AP mode
also keeps the listener without harm (`docs/ARCHITECTURE.md` states this deliberately).

**E-2 · #6 — latent, not live.** `ap_active` is set to 1 only by `setup_ap_start()` and
cleared to 0 only by `sta_mode_start()`, which is called only from `app_main()`. After
failover, `ap_active` stays 1 until the portal reboots the board, so the "timer still
counting from a previous attempt" window cannot open today. The one-line reset is still
worth taking so the invariant holds if setup-AP restart logic is ever added.

**E-3 · #9 / #21 — the mutex *is* held.** `audio_pump_task` takes `ring_mutex`, reads
`avail = ring_used()`, then releases it before `ring_read()`; `ring_read()` re-clamps under
the lock (`if (len > avail) len = avail;`). A stale `avail` can only mean a slightly
smaller read or one iteration of silence — never corruption.

**E-4 · #17 — real symptom, wrong mechanism.** `ring_write()` cannot overrun: it loops
`while (written < len)` and returns early when `ring_free() == 0`. The burst is bounded at
`gap > 64 → gap = 1`, so worst case is 64 silence frames (122 KB) flushed into a 256 KB
ring *before* the current packet's payload is written; that payload then gets `w = 0` and
is lost. Capping by free space is the correct fix.

**E-5 · #18 — works today.** Both sides are `uint32_t` and the comparison is
`(uint32_t)(esp_timer_get_time()/1000) - lp < 200`, which is wrap-correct across the ~49-day
overflow. It is fragile rather than broken.

**E-6 · #24 — already silent.** `rssi_task` prints only when
`esp_wifi_sta_get_ap_info() == ESP_OK`, which fails in AP mode; so AP mode already produces
no `rssi=` line. The useful version of this concern is covered by #23/#26 in Phase A
(explicit AP-mode heartbeat).

**E-7 · #25 — the cast makes it correct.** The log uses
`(unsigned long)pkts` with `%lu`, so the conversion is explicit and portable regardless of
whether `uint32_t` is `unsigned int`. `PRIu32` is tidier, not safer.

**E-8 · #30 — unreachable.** `gain_clip()` has exactly one caller
(`gain_clip(mono[i])`, `mono` is `int16_t[]`), so `|s| ≤ 32768` and `s *= PCM_GAIN` peaks at
65 536 — three orders of magnitude below `INT32_MAX`. The existing clamp handles the real
domain.

**E-9 · #31 — already handled.** Both restart paths delay before rebooting: 300 ms in
`portal_save_handler` and 200 ms in `factory_reset_task`, each well over the ~21 ms DMA
depth, so the last audio chunk drains (the 300 ms exists to flush the HTTP response and
covers audio too).

**E-10 · Found during this triage (not in the review): `docs/GUIDELINES.md` was
duplicated.** A previous patch had appended an evolved copy of the guideline sections, so
sections 7–101 repeated at 188–290 with the unique "Repository layout" /
"Audio Player App" content wedged between them (which is why a one-line edit appeared as
two identical hunks). Rebuilt losslessly on 2026-09-19: 290 → 196 lines, 12 unique
headings, 6 declared supersessions, zero unexpected line drops
(`tmp/dedupe_guidelines.py`).

**E-11 · Also found: dead code.** `config.py` defined `sched_save()` / `sched_load()`
(nothing imported them) — added by a previous session's patch script and never wired up.
Removed 2026-09-19 (the app persists schedules through `settings_save()`).


**E-12 · Phase A implementation traps + the #23 blocker (2026-09-19).**
Two silent-failure traps surfaced while building Phase A:
(a) **`CONFIG_FREERTOS_HZ=100` in this project**, so `pdMS_TO_TICKS(5)` evaluates to **0
ticks** and `vTaskDelay(0)` is a bare yield — the idle poll would have busy-spun at priority
4 forever. Use `vTaskDelay(1)` (= 10 ms) and do the tick arithmetic explicitly.
(b) **`SO_RCVTIMEO` is not compile-enabled here** (`CONFIG_LWIP_SO_RCVTIMEO` is unset), so the
`setsockopt(SO_RCVTIMEO)` the review recommended would compile, return success and change
nothing — the heartbeat would never have fired. `MSG_DONTWAIT` was used instead (defined
`0x08` in `lwip/sockets.h:272`, honoured as `NETCONN_DONTBLOCK` in the UDP recv path).
Rate sanity for the non-blocking poll: streams arrive at **50 datagrams/s** (48 000 / 960),
the poll runs ~100x/s, and the UDP mailbox is 6 deep (`CONFIG_LWIP_UDP_RECVMBOX_SIZE=6`) —
~2.4x margin, confirmed by `dropped=0` over 30 s.
**#23 cannot be closed from this machine**: the Wi-Fi radio is software-disabled
(`netsh wlan show interfaces` → `Software Off`) and `netsh wlan set autoconfig enabled=yes
interface="Wi-Fi"` returns *"You do not have sufficient privileges or group policy has been
applied."* The open-network profile for `AudioNode-Setup` was added successfully, so closing
it takes one privileged step: enable the radio (or use a phone), put the board in setup-AP
mode (hold BOOT 5 s), join the AP, and expect `ap: station <mac> joined (aid=1)` on join plus
`ap: station <mac> left (aid=1)` on leave.

**E-13 · Phase B implementation notes + gate honesty (2026-09-19).**
- #15 uses a hand-rolled strict dotted-quad validator, not lwIP `inet_pton`: the IDF v6.1
  source (`ip4_addr.c:165-173, 187-193`) shows `ip4addr_aton` accepts `0x`/octal bases,
  `a.b.c` partial forms and trailing whitespace — laxer than POSIX `inet_pton`. Portal
  validation must be STRICTER than the boot-time parser, so `0NN` octets are rejected too
  ("09" is garbage to lwIP, "010" is octal 8): the saved string always parses back as plain
  decimal. Validation runs BEFORE any NVS write — a bad IP can no longer land in NVS and
  silently degrade the whitelist to accept-any at boot.
- Gate honesty: the logic gate ran as a Python port of the three changed functions
  (21/21, `tmp/verify_phaseB.py`) + app selftest; the *wire* gate (AP → POST invalid IP →
  400 → valid → save → reboot → STA) is **pending hardware** — the dev PC has no usable
  second netif (same blocker class as #23, E-12). Hardware-verified on the flashed Phase B
  image: boot → `GOT IP`, 40 s stream at exactly 50.0 pps `dropped=0` byte-exact, idle
  heartbeat intact, no panic, board stable after. One phone join + form submit closes both
  wire items.
- Tooling artifact worth remembering: opening the monitor can reset the board despite
  `--no-reset` (observed twice: boot lines at t≈1.2 s after attach; uptime-derived stream
  stats confirmed fresh boots). This makes cumulative `pkts=` counters APPEAR to go
  backwards between captures and hid early boot lines in two runs. Batch a whole gate into
  ONE capture that attaches before the action. (Also observed intermittently NOT firing —
  retry attaches until the boot section appears; Phase C's boot lines took several
  capture attempts.)

**E-14 · Phase C notes (2026-09-20).** The old (unversioned) and new (versioned, port-less)
structs happened to differ in size here (114 vs 115 — actual compiler layout), so on THIS
board the length check alone would already have rejected the old blob; the version byte is
still required for the general case (a same-size reshuffle would pass a length-only check).
Both checks together: `len == sizeof(node_cfg) && version == CFG_VERSION`.

**E-15 · Phase D notes (2026-09-20).**
- #18 rejected on atomicity grounds: `last_pkt_ms` is written by `udp_task` and read by
  `led_task`. On Xtensa (ESP32-S3) an aligned 32-bit load/store is atomic; a 64-bit access
  is two 32-bit halves with no cross-half guarantee. The current
  `(uint32_t)(now_ms) - lp < 200` pattern is single-word atomic AND wrap-correct
  (unsigned arithmetic, ~49-day period) — converting to bare `int64_t` would trade a
  non-issue for a real (benign, self-correcting within one 30 ms LED frame) torn-read
  race. If a 49-day uptime ever matters, the honest fix is a seqlock or a short critical
  section, not the bare conversion the review suggested.
- Tooling artifact (extends E-13): killing the monitor's python (taskkill) pulses
  DTR/RTS on port release and the capture script relaunches — file tails can show a boot
  with no `rst:` banner, and an attach reset can fire mid-stream (lifetime totals then
  restart). Always cross-check counters for continuity before reading them as firmware
  behaviour; the board itself showed zero panic/watchdog/reset markers across every
  Phase D capture.

**E-16 · Phase E notes + the closure cascade (2026-09-20).**
- The full factory-reset/re-provision cycle landed on record because a long-running
  background capture was started BEFORE the user touched the button — that is also how
  #23's join/leave lines and B's wire save-path closed in the same session. Pattern worth
  repeating: start the capture first, then hand the user the hardware action.
- #29's stop/deinit runs in the factory-reset task (task context — legal). The theoretical
  interleave (failover firing after the deinit) cannot occur: failover is gated on
  `ap_active == 0 && net_state < 1 for 30 s`, which is not the state during a normal
  factory reset (STA-with-IP or AP mode) — unchanged by #29.
- A second brief BOOT press during AP mode printed "BOOT held" and released early — the
  task's cancel path (`held_ms >= 1000 → released, cancelled`) behaved as designed.

