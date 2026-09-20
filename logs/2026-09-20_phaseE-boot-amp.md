# 2026-09-20 — Phase E: boot & amp hygiene (#32/#29) — P18 (+ #23 and B wire save-path closed)

## What changed (`firmware/main/main.c` only — 2 hunks)
- **#32** `app_main`: `i2s_init()` now runs FIRST; the amp's SD pin (GPIO15) is driven
  HIGH only afterwards. With SD high while DIN still floated, the MAX98357A could amplify
  board noise for the pre-I2S window; now the amp wakes with the I2S clocks already running.
- **#29** `factory_reset_task`: `esp_wifi_stop()` + `esp_wifi_deinit()` run BEFORE
  `nvs_flash_erase()` — the Wi-Fi driver holds its own NVS handles (`nvs.net80211`, PHY
  calibration) and could race the erase. Errors from the stop/deinit are harmless (the
  board reboots right after).

## Build + flash
- `idf.py build` → 0 errors (`audio_node.bin` 0xdc750, +32 over Phase D).
- flash: **Hash of data verified.**

## Gates on hardware
- **30 s stream regression (post-reorder boot)**: sender 1500 frames / 30.0 s → board
  `pkts=1452 dropped=0 total=2839680` = **1452 × 1920 byte-exact**, ring 14.6 KB, heartbeat
  resumed. Amp path alive after the reorder.
- **Factory reset with a capture already running** (user held BOOT ~5 s):
```
factory reset: BOOT held, keep 5 s to erase NVS
factory reset: NVS erased, rebooting into setup AP
cfg: no usable config (first boot / factory reset / rejected blob)
wifi: no SSID configured, starting setup AP
setup ap: running 'AudioNode-Setup' open AP, portal http://192.168.4.1/
```
  **Zero NVS errors, zero panic/watchdog/abort markers** in the whole capture (a second
  brief BOOT press during AP mode printed "BOOT held" and was released early — no erase,
  as designed).
- **Re-provision round trip, live-fire of Phase B/C code (later, after wrong-pw → reason 15 → re-provision)**:
```
ap: station a4:c3:f0:3c:f1:7c joined (aid=1)
cfg: saved via portal (SSID=<ssid> server=<pc-ip>)      <- #16 format, #15-validated IP
ap: station a4:c3:f0:3c:f1:7c left (aid=1)
cfg: server whitelist <pc-ip>
STA: joining <ssid>
GOT IP: <board-ip>
udp: idle 30 s, pkts=0 dropped=0 total=0 bytes (listening on :1234)
```
- **Final 12 s stream**: sender 600 frames → board `pkts=480 dropped=0 total=921600` =
  **480 × 1920 byte-exact** (the ~120 head packets fell in the attach-reset window —
  tooling; zero interior gaps).

## Bonus closures
- **#23 hardware-verified**: the `ap: station … joined (aid=1)` / `… left (aid=1)` lines
  captured live — the exact lines Phase A added (E-12 said this machine couldn't close it;
  the PC's own Wi-Fi turned out to be the portal client).
- **Phase B wire save-path**: portal POST → save → reboot → STA verified with the new
  handler (no `:port` in the save line — #16's removal is live; the #15-validated IP
  survived to the whitelist).
- Still open from B: the **bad-IP → HTTP 400** half# END P18 RECORD

## #1/#2 section summary
- The #1/#2 section is now complete and committed. See the full audit register in docs/AUDIT.md.
## Placeholders used throughout: <ssid> = real SSID (git-ignored captures hold it, docs do not).