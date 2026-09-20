# 2026-09-20 — Phase C: NVS config versioning (#12/#13) + server_port removal (#16) — P16

## What changed (`firmware/main/main.c` only — 7 hunks)
- **#12** `node_cfg_t` gained `uint8_t version` as the first field, `#define CFG_VERSION 2`;
  `cfg_save()` stamps it before every write.
- **#13** `cfg_load()` now requires `len == sizeof(node_cfg)` AND `version == CFG_VERSION`
  on top of `nvs_get_blob == ESP_OK`. Reason (verified in IDF v6.1 `nvs_api.cpp`): a
  SHORTER stored blob is copied into the caller's buffer and returns **OK** (stale tail),
  only a LONGER one errors — ESP_OK alone proves nothing. On mismatch: log
  `want v2 len 115, got v%u len %u`, `memset` the struct, return `ESP_ERR_NOT_FOUND`.
- **#16** `server_port` deleted: struct field, portal form input, handler `vals[3]` copy
  and the `server=%s:%u` print. The board always listened on `UDP_PORT` (1234); the value
  was stored and displayed but consumed by nothing. Decision (b) from AUDIT.md.
- app_main's message updated: `cfg: no usable config (first boot / factory reset /
  rejected blob)`.

## Build + flash
- `idf.py build` → 0 errors (`audio_node.bin` 0xdc520, +320 over Phase B).
- flash: **Hash of data verified.**

## Hardware gate — old-blob rejection, verified live
```
cfg: nvs blob rejected (want v2 len 115, got v77 len 114) -> re-provision
cfg: no usable config (first boot / factory reset / rejected blob)
wifi: no SSID configured, starting setup AP
setup ap: running 'AudioNode-Setup' open AP, portal http://192.168.4.1/
```
`v77` = `0x4D` = `'M'` — the first byte of the old (unversioned) blob's SSID string read
as the version byte. That is exactly the silent-garbage failure mode #12 exists to guard
against; the rejection did not panic, did not half-apply, and fell back to a clean setup AP.
- Note: old struct was actually **114** bytes (not the 116 my padding estimate guessed);
  new struct is 115. So on this board a length-only check would ALSO have rejected — the
  version byte remains required for the general case (a same-size reshuffle would pass a
  length-only check). (AUDIT.md E-14.)
- Capture note: the attach-reset fired only on the ~6th capture attempt this session —
  retry attaches until the boot section appears.

## Gate honesty / current board state
- Verified on hardware: rejection → clear log → setup AP fallback (the NEW code path).
- **Pending (needs one Wi-Fi client on `AudioNode-Setup`, ~2 min)**: the re-provision
  itself — this is now REQUIRED for streaming (the version gate rejects the old v1 blob by
  design; the blob is intact in NVS, not lost). The same session closes #23 (join/leave
  lines), the Phase B wire gate (400 on bad IP / save on valid), and verifies the v2
  save→load round trip. Steps: PROJECT_STATE §11 item 13.
- Factory-reset path unchanged (`nvs_flash_erase` on BOOT hold); not re-run today since the
  board is already unprovisioned (same code path as first-boot, which the gate exercised).

## Re-provision done (2026-09-20 evening) — Phase C round trip CLOSED
User provisioned via `192.168.4.1` (from this PC's own Wi-Fi — the adapter took a DHCP
lease at 192.168.4.2 from the board's AP, so the "no second netif" blocker is gone for any
future portal session). Post-provision boot capture:
```
cfg: server whitelist <pc-ip>        <- v2 blob loaded, no rejection line
STA: joining <ssid>
GOT IP: <board-ip>
```
Streaming regression on the flashed image (whitelist active, source = provisioned server IP):
- run 1: sender 1250 frames / 25.0 s (50.0 fps) → board `pkts=1154 dropped=76`,
  total 2215680 = 1154 × 1920 **byte-exact**
- run 2: sender 1000 frames / 20.0 s → board `pkts=979 dropped=21`, total 1879680 **byte-exact**
2-6% air loss today (seq-gap silence-fill handled it; rssi dipping to -63) vs 0% in the
Phase B session on the identical RX path — environmental, not code. Still open, needs the
board in setup-AP mode again (whenever that naturally happens): (#23) capture the
`ap: station joined/left` lines (the provisioning join happened before a capture was
attached) and (B) the bad-IP → HTTP 400 wire test.

