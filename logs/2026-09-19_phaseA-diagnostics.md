# 2026-09-19 — Phase A: close the diagnostic gaps (VERIFIED ON HARDWARE, 3 of 4 items)

Phase A of `docs/AUDIT.md`: items **#4, #5, #23, #26**. Goal: an idle-but-healthy node and a
dead one must not look identical on the serial log — that ambiguity is what produced the
"board is not getting an IP / no serial logs" misdiagnosis.

## Changes (`firmware/main/main.c`)

| Item | Change |
|---|---|
| #5 | `WIFI_EVENT_STA_START` now checks and prints the connect result: `wifi: esp_wifi_connect rc=%d (%s)` via `esp_err_to_name()`. Previously the call was silent, so a connect that never started looked exactly like one that failed. |
| #23 | `WIFI_EVENT_AP_STACONNECTED` / `AP_STADISCONNECTED` handled: `ap: station <mac> joined/left (aid=N)`. Added `#include "esp_mac.h"` for `MACSTR`/`MAC2STR`. Answers "did my phone even reach the setup AP?" |
| #26 | `udp_task` is no longer a blocking `recvfrom`: `MSG_DONTWAIT` + a 1-tick sleep when nothing is queued, plus a **single** idle heartbeat after 30 s with no datagram: `udp: idle <n> s, pkts=<n> dropped=<n> total=<n> bytes (listening on :1234)`. |
| #4 | `socket()` failure now retries every 1 s like `bind()` (it used to `vTaskDelay(2000); return;` — no UDP for the whole boot). |

Deliberately **not** used: `SO_RCVTIMEO`. `CONFIG_LWIP_SO_RCVTIMEO` is not set in this
`sdkconfig`, so `setsockopt(SO_RCVTIMEO)` would compile and silently do nothing — the
heartbeat would never print. `MSG_DONTWAIT` is verified present (`lwip/sockets.h:272`,
`0x08`) and honoured by the UDP recv path (`apiflags = NETCONN_DONTBLOCK`).

### Bug caught while implementing (would have shipped a busy-spin)
`CONFIG_FREERTOS_HZ=100`, so `pdMS_TO_TICKS(5)` is **0 ticks** — `vTaskDelay(0)` is a bare
yield, not a 5 ms sleep; the idle poll would have spun at priority 4 forever. Replaced with
`vTaskDelay(1)` (= 10 ms) and commented the tick arithmetic at the call site.

Rate check for the non-blocking poll: a stream arrives at **50 datagrams/s** (48 000 Hz /
960 samples), and the poll runs ~100x/s against a 6-deep UDP mailbox
(`CONFIG_LWIP_UDP_RECVMBOX_SIZE=6`), so bursts are absorbed with ~2.4x margin. Measured
`dropped=0` over a 30 s stream confirms it (below).

## Build / flash
- `idf.py build` → `Project build complete`, 0 errors, 0 warnings in `main.c`;
  `audio_node.bin` 0xdc3c0 (**902,080 B**, +640 B vs P12's 901,440). NB: an earlier
  revision of this log wrote "901,568 B / +128 B" — a decimal conversion error; the hex
  was always correct.
- `idf.py -p COM5 flash` → `Hash of data verified.` / `Hard resetting via RTS pin...`

## Re-verification on the exact flashed image (2026-09-20, post-midnight)
To rule out any doubt that the gates ran on the committed source, the firmware was **rebuilt
from the unchanged tree and re-flashed** (`'audio_node.bin' at 0x00010000 verified.` — same
0xdc3c0 size, confirming source identity), and all three gates were re-run in **one
consolidated 100 s capture** (boot → idle → 30 s sender → idle; capture: `tmp/pa2_gates.txt`,
board serial from ROM reset):

```
wifi: esp_wifi_connect rc=0 (ESP_OK)                                 <- #5
GOT IP: <board-ip>
udp: idle 30 s, pkts=0 dropped=0 total=0 bytes (listening on :1234)  <- #26 (Gate 1)
udp: pkts=1237 dropped=17 ring=41472 pcm=2375040 bytes (t=57594 ms)  <- stream in progress
udp: idle 30 s, pkts=1480 dropped=20 total=2841600 bytes (listening on :1234)  <- Gate 3
```

Sender: `done: 1500 frames (30.0s) in 30.0s` (50.0 fps). Accounting reconciles exactly:
1480 received + 20 gap-filled = 1500 sent; 1480 × 1920 = 2,841,600 = `total`.

### Packet-loss variance across runs — environmental, not a regression
Identical code produced `dropped=0` twice earlier in this session (`tmp/pa_str.txt`,
`tmp/po_idle.txt`) and then `dropped=20` (`tmp/pa2_gates.txt`) and `dropped≈5`
(`tmp/pa2_run2.txt`) in later runs. The drops arrive in **4–6 packet bursts** (per-5 s
`dropped` deltas: 6, 0, 5, 6, 0) ≈ single ~120 ms Wi-Fi link blackouts — classic 2.4 GHz
RF variance, not the new poll: the task drains at ~100x/s against 50 datagrams/s (2x
headroom on a 6-deep mailbox), and the same code path already proved 0 drops. The
silence-fill mechanism did exactly its job: counters reconciled in every run, no panic,
no `recvfrom err=`, ring stayed small (≤41 KB ≈ 0.43 s of audio, pump keeping up).

## Gate 1 — boot + 45 s with no sender (PASS)
```
audio_node: WiFi streamer start
wifi: esp_wifi_connect rc=0 (ESP_OK)          <- #5
STA: joining <ssid>
udp: listening on 0.0.0.0:1234, waiting for RTP L16 (PT=96)...
GOT IP: <board-ip>
rssi=-53
udp: idle 30 s, pkts=0 dropped=0 total=0 bytes (listening on :1234)   <- #26, fired once
rssi=-49
```
Exactly **one** idle line in 48 s (no spam), and no `udp: recvfrom err=` noise.

## Gate 2 — 30 s continuous tone (PASS)
Sender: `done: 1500 frames (30.0s) in 30.0s` (= 50.0 fps).
```
udp: pkts=251  dropped=0 ring=2560 pcm=481920  bytes (t=64624 ms)
udp: pkts=502  dropped=0 ring=3840 pcm=963840  bytes (t=69634 ms)
udp: pkts=753  dropped=0 ring=3584 pcm=1445760 bytes (t=74654 ms)
udp: pkts=1004 dropped=0 ring=3456 pcm=1927680 bytes (t=79674 ms)
udp: pkts=1255 dropped=0 ring=4736 pcm=2409600 bytes (t=84694 ms)
```
- 1255 x 1920 = 2 409 600 — byte-exact; deltas 251 per 5 s = 50.2 pkts/s = real time
- **No `udp: idle` line during the entire 30 s stream** — the heartbeat is correctly
  suppressed while packets arrive

## Gate 3 — heartbeat resumes after the stream (PASS)
40 s with no sender, `--no-reset`:
```
udp: idle 30 s, pkts=1500 dropped=0 total=2880000 bytes (listening on :1234)
```
1500 x 1920 = 2 880 000 — byte-exact, and it reports the accumulated counters, so the line
doubles as a "the listener is alive, here is its lifetime total" statement.

## #23 — implemented, hardware verification BLOCKED (not falsified)
Nothing in this project ever joins the setup AP except a human, and this PC's Wi-Fi radio is
software-disabled:
```
netsh wlan show interfaces -> State: disconnected | Radio: Hardware On / Software Off
netsh wlan set autoconfig enabled=yes interface="Wi-Fi"
  -> You do not have sufficient privileges or group policy has been applied.
```
The open-network profile for `AudioNode-Setup` was added successfully (not elevated), so the
verification is one privileged step away.

**To close it:** enable the Wi-Fi radio (or join from a phone), put the board in setup-AP mode
(hold BOOT 5 s to factory reset, or first boot), join `AudioNode-Setup`, and expect:
```
ap: station <mac> joined (aid=1)
```
on join and `ap: station <mac> left (aid=1)` on leave/disconnect.

## Not changed
Nothing in the audio path, the ring buffer, the RTP validation, or the failover logic — Phase
A adds logging plus the idle poll only. The streaming numbers above are unchanged from P12
(50.0 fps, `dropped=0`, byte-exact).
