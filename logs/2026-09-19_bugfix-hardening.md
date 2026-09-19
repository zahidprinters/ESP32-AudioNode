# 2026-09-19 — Firmware robustness fixes (4 reported bugs) — VERIFIED ON HARDWARE

## What was reported
Four bugs, ordered by the reporter as "most critical to least":
1. `portal_save_handler` — 1-byte write past `char body[1024]` (buffer overflow)
2. `wifi_event_handler` — disconnect reason code discarded
3. `app_main` — `IP_EVENT_STA_LOST_IP` never registered
4. `udp_task` — `bind()` failure returned silently, killing UDP forever

## Pre-change baseline (ground truth, captured before touching code)
Boot with reset (`idf.py -p COM5 monitor`):

```
audio_node: WiFi streamer start
I2S: 48000 Hz, 16-bit mono, BCLK=4 LRC=5 DIN=6 SD=15 RGB=48
STA: joining <ssid>
wifi: STA mode, power-save OFF, listening on :1234
udp: listening on 0.0.0.0:1234, waiting for RTP L16 (PT=96)...
wifi:connected with <ssid>, aid = 1, channel 2, rssi: -42
esp_netif_handlers: sta ip: <board-ip>
GOT IP: <board-ip>
rssi=-46
```

**Finding: the board was already healthy.** It had an IP, `bind()` succeeded on the
first attempt, and it was idle only because no sender was running. The premise of
bug 2 ("why you're not getting an IP") was not reproducible — the disconnect reason
code has nothing to report when no disconnect ever happens.

12 s RTP tone sent to it (pre-change firmware, `send_pcm.py tone <board-ip> 1234 12 1000 0.5`):

```
udp: pkts=251 dropped=0 ring=2304 pcm=481920 bytes (t=69958 ms)
udp: pkts=502 dropped=0 ring=2560 pcm=963840 bytes (t=74974 ms)
rssi=-44
```

502 x 1920 = 963840 — byte-exact, `dropped=0`. Audio path fully functional.

## Change made (all four fixes, one build)
| # | Fix |
|---|---|
| 1 | Loop bound `off < (int)sizeof(body)` -> `(int)sizeof(body) - 1`; also read in chunks (`sizeof(body) - 1 - off`) instead of 1 byte/iteration, so the terminator byte always fits |
| 2 | `WIFI DISCONNECTED: reason=%d` — reason code now printed (`wifi_event_sta_disconnected_t`) |
| 3 | `IP_EVENT_STA_LOST_IP` handler registered + `IP_EVENT_STA_LOST_IP` case added (`net_state = 0`) |
| 4 | `bind()` failure now retries once per second instead of `close(sock); return;` |

## Build
`idf.py build` -> `Project build complete`, 0 errors, 0 warnings in main.c.
`build/audio_node.bin` 0xdc140 (901,440 B — +208 B vs the committed image; the new
logging accounts for it). 0x23ec0 bytes (14%) free in the app partition.

## Flash
`idf.py -p COM5 flash` -> `Hash of data verified.` / `Hard resetting via RTS pin...`

## Post-change verification (boot + 12 s RTP tone)
```
rst:0x15 (USB_UART_CHIP_RESET),boot:0x8 (SPI_FAST_FLASH_BOOT)
audio_node: WiFi streamer start
I2S: 48000 Hz, 16-bit mono, BCLK=4 LRC=5 DIN=6 SD=15 RGB=48
STA: joining <ssid>
udp: listening on 0.0.0.0:1234, waiting for RTP L16 (PT=96)...
GOT IP: <board-ip>
udp: pkts=77  dropped=0 ring=2944 pcm=147840 bytes (t=5015 ms)
udp: pkts=327 dropped=0 ring=3712 pcm=627840 bytes (t=10015 ms)
rssi=-50
```
Sender: `done: 600 frames (12.0s) in 12.0s` (= 50.0 fps, real time).

- 327 x 1920 = 627840 — byte-exact, `dropped=0`
- `udp: listening on ...` printed with **no** `bind failed ... retrying` line -> bind
  still succeeds first try; the retry loop is inert on healthy hardware (no regression)
- `GOT IP` still fires -> the added `LOST_IP` registration did not disturb `GOT_IP`
- No `WIFI DISCONNECTED` and no `IP_EVENT_STA_LOST_IP` lines — none occurred in 25 s
- No panic / abort / assert

## Conclusion
All four fixes are in and the streaming path is unchanged and verified. Bug 1 was a
genuine memory-safety defect (unreachable via the portal form, which posts ~90 bytes,
but reachable by any hand-crafted POST of exactly 1024+ bytes). Bugs 2-4 are
diagnostics/robustness: they make a future failure visible and survivable rather than
fixing a fault present today. The "not getting an IP" symptom was not reproducible on
this hardware — the node was simply idle with no sender running.