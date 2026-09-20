# 2026-09-19 — Phase B: portal input hardening (audit #15/#14/#27/#11) — P15

## What changed (`firmware/main/main.c` only — 4 hunks)
- **#15** `server_ip` is validated by `valid_ipv4()` (strict dotted-quad) **before any NVS
  write**; failure → `HTTPD_400_BAD_REQUEST` "server IP is not a valid IPv4 address …
  nothing was saved". Old behaviour: a malformed IP saved fine, then boot silently degraded
  the whitelist to accept-any (`cfg_apply_server_whitelist` → `inet_pton` failed).
  Deliberately **stricter** than the boot parser: IDF v6.1 `ip4addr_aton`
  (`ip4_addr.c:165-193`) also accepts `0x`/octal bases, `a.b.c` partials and trailing
  whitespace; the validator additionally rejects `0NN` octets ("09" = garbage to lwIP,
  "010" = octal 8) so anything saved parses back as plain decimal.
- **#14** `strlen(src)` hoisted out of the `url_decode` loop (O(n²) → O(n)).
- **#27** `char *html` → `const char *html` (pointer to a string literal).
- **#11** `strtok_r` loop rewritten idiomatically: `strtok_r(body, "&", &save)` first,
  `strtok_r(NULL, "&", &save)` after (the old `tok = save` chain worked but was fragile).
- **#16** (`server_port` stored-but-unused) **re-slotted to Phase C** — it changes
  `node_cfg_t`/the NVS blob, which is exactly what C's version field gates. Decision on
  record: delete the field (nothing consumes it).

## Logic gate — `tmp/verify_phaseB.py` (ports of the three changed functions)
```
python tmp\verify_phaseB.py
...
ALL 21 CHECKS PASSED
```
Covers: validator accept set (incl. `10.0.0.1` so the 0NN guard can't reject "10"),
octet-255 / 0NN / 5-octet / empty-octet / garbage-char / space / empty-string rejects,
`url_decode` round trips (incl. `%26` → `&` surviving tokenisation, incomplete escape),
full form reassembly, empty-token skipping, and the idiomatic `strtok_r` source form.

App selftest (Python311): **all checks passed**.

## Build + flash
- `idf.py build` → 0 errors.
- flash: `'audio_node.bin' at 0x00010000` → **Hash of data verified.**

## Hardware gates (on the flashed Phase B image)
- **Boot**: WiFi join → `sta ip: <board-ip>` → `GOT IP: <board-ip>` at t≈4.3 s board time,
  rssi flowing. No panic.
- **40 s tone**: sender `done: 2000 frames (40.0s) in 40.0s` (50.0 fps). Board 5 s stats:
  `pkts=1329 (t=30054 ms) → 1579 (t=35054) → 1829 (t=40054)` = **+250 per 5.0 s = exactly
  50.0 pps, dropped=0**, ring steady ~10-11 KB. Final count extrapolates ≈1996/2000 — the
  ~4 head packets fell before stats logging began (see artifact below); no interior gaps.
- **Heartbeat**: single `udp: idle 30 s, pkts=0 …` when no sender; silent during the stream;
  resumes with lifetime totals after. Phase A behaviour intact.
- **Stability**: post-stream captures show rssi lines only — no boot lines, no panic.

## Tooling artifact (recorded in AUDIT.md E-13 — cost us two misreadings today)
Opening the monitor can **reset the board despite `--no-reset`** (observed twice: full boot
at t≈1.2 s after attach). Consequences: cumulative `pkts=` counters appear to go BACKWARDS
between captures (fresh boot), and early boot lines vanish when the attach races the flash
port release. The "counter went down ⇒ crash" reading was wrong — uptime-derived stream
stats (`t=30054 ms` etc.) proved fresh boots. **Rule: batch a whole gate into ONE capture
that attaches before the action.**

## Gate honesty
- Verified: logic gate 21/21 + selftest; hardware boot/stream/heartbeat/stability on the
  flashed image.
- **Pending hardware**: the portal *wire* round-trip (POST invalid IP → 400 + nothing
  saved; POST valid → save → reboot → STA). The dev PC has no usable second netif (same
  blocker class as #23, AUDIT.md E-12). One phone join + form submit to `AudioNode-Setup`
  closes both — see PROJECT_STATE §11 item 13.
