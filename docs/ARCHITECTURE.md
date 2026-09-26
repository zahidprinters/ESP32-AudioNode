# Architecture — AudioNode WiFi speaker box

## Purpose

A configurable, networkable speaker: an ESP32-S3 board with a MAX98357A class-D amp, plus an onboard WS2812 RGB LED. Drop it on any WiFi, point it at a server, and it plays PCM audio over RTP/UDP. Multiple boards can share one server stream.

## Stack

| Layer | Technology | Version | Notes |
|---|---|---|---|
| Board | ESP32-S3-DevKitC-1-N8R2 | — | 8 MB flash, 8 MB octal PSRAM; the jitter ring lives in PSRAM |
| Firmware | ESP-IDF | 6.1 | C, FreeRTOS; target `esp32s3`; the whole app is `firmware/main/main.c` |
| Component | `espressif/led_strip` | ^3.0.0 | the WS2812 driver, pinned by `dependencies.lock` |
| Amplifier | MAX98357A | — | I2S in, speaker out; no MCLK, 3 dB minimum gain |
| Server | Python + Flask + Flask-SocketIO | 3.11+ | `audio_player/`; threading mode, no eventlet |
| Decode | ffmpeg via `imageio-ffmpeg` | — | static binary, nothing installed system-wide |
| Transport | RTP L16 over UDP | PT 96 | the one interface between the two halves |

## Layout

| Path | What it holds |
|---|---|
| `firmware/` | ESP-IDF project for the board; `main/main.c` is the entire application |
| `audio_player/` | the PC server: web app, RTP pipeline, library scan, bench sender, self-check |
| `tools/env.ps1` | ESP-IDF environment for one specific Windows install |
| `docs/` | architecture, function map, setup, guidelines, project state |
| `logs/` | git-ignored session scratch plus `app.log` |
| `tmp/` | git-ignored experiments |

The two halves share nothing but the wire format. Firmware code stays in
`firmware/`, server code stays in `audio_player/`.

## Key modules

| Module | Responsibility |
|---|---|
| `firmware/main/main.c` | everything the board does: config, Wi-Fi, portal, RTP receive, ring, I2S, LED |
| `audio_player/player.py` | the single ffmpeg → RTP L16/UDP pipeline: pacing, filter chain, seek |
| `audio_player/app.py` | Flask + Socket.IO: REST routes, WebSocket pushes, scheduler, discovery |
| `audio_player/config.py` | every tunable plus the nodes / EQ / settings persistence |
| `audio_player/selftest.py` | the runnable check; exits non-zero on failure |
| `audio_player/deps.py` | the dependency contract, verified on every entry point |

## Data flow (end to end)

```
Server (audio_player: browser app, or CLI send_pcm.py; VLC/custom possible)
  │  reads audio: file (ffmpeg) / PC loopback (WASAPI) / tone
  │  encodes to RTP L16: 48 kHz, 16-bit, mono, 20 ms frames
  │  RTP header: version=2, PT=96, seq+1/frame, ts+960/frame, SSRC=rand
  │  paces to real time (see "Pacing" below) — one datagram per frame per node
  └─► UDP datagram ──► board IP :1234

  ESP32-S3 (firmware)
  │  WiFi: setup AP (first boot/factory-reset/failover) OR STA (normal)
  │  UDP socket on port 1234
  │  RX task: recv UDP → validate RTP → put PCM into PSRAM ring buffer
  │  audio task (pump): pull PCM from ring → I2S TX → MAX98357A
  │  LED task: red / blue-breathing / VU meter by state + level
  │  setup task: AP + web portal + NVS config + factory reset (GPIO0)
  └─► I2S BCLK/LRC/DIN ──► MAX98357A ──► speaker
```

Code lives in two trees: `firmware/` (the board, all of the ESP32 side) and
`audio_player/` (the server, all of the PC side). `audio_player/player.py` is the
single ffmpeg→RTP implementation — the browser app and the CLI sender both use it.

The audio pipeline (I2S, PSRAM ring buffer, DMA-backpressure pump, ×2 gain, LED) is carried from the proven TCP prototype (M0–M3). Only the transport layer changes from TCP to RTP/UDP.

## Pacing (why the sender must be rate-limited)

The board's jitter ring overflows and drops packets if the server sends faster
than real time, and it underruns (audible gaps) if the server sends slower.
Correct pacing is one frame every 20 ms = **50 datagrams/s per node**, measured
from the first frame actually sent:

```python
sent_frames = bytes_sent / 1920
ahead = (sent_frames / 50) - (now - first_frame_time)
if ahead > 0:
    time.sleep(min(ahead, 0.25))   # sleep off the whole lead, capped per iteration
```

Two traps worth remembering (both hit in production here):

- The clock must be anchored on the **first sent frame**, not on `play()` —
  ffmpeg spawn + decode takes ~250 ms and would otherwise look like a deficit.
- An upper bound on `ahead` (e.g. `0 < ahead < 0.1`) *looks* like a safety net but
  silently disables pacing as soon as the sender runs >100 ms ahead, which is
  immediately (ffmpeg hands the pump 4 frames per read). The sender then free-runs
  at the decode rate (~3×) and the board logs `dropped=N`.

Verification is cheap and automatic: `python -m audio_player.selftest` measures the
real send rate over a loopback UDP socket (expects ~50 frames/s).

## Protocol: RTP L16 over UDP

**Payload**: PCM 16-bit little-endian, 48 000 Hz, mono.

**Frame**: 20 ms = 960 samples = 1 920 PCM bytes per frame.

**RTP header** (per datagram):

| Field | Value |
|---|---|
| Version | 2 |
| Padding | 0 |
| Extension | 0 |
| CSRC count | 0 |
| Marker | 0 |
| Payload type | 96 (dynamic — L16/48k/mono) |
| Sequence number | +1 per frame |
| Timestamp | +960 per frame (units = samples, not ms) |
| SSRC | fixed random value per sender |

**UDP**: destination = board IP :1234. Source IP must match the configured server IP (whitelist).

**Timestamp semantics**: the RTP timestamp counts samples, so at 48 kHz each 20 ms frame advances the timestamp by exactly 960. This makes sender/receiver behavior unambiguous — a missed frame means the receiver sees the next timestamp jump by 2×960, which it detects as a gap.

## Packet validation (receiver)

The board's UDP RX task validates each datagram before feeding it to the ring buffer. A datagram that fails any check is discarded and the loss is silence-filled and counted.

Checks, **in the order the firmware applies them** (`udp_task` in `firmware/main/main.c`):

1. **Datagram length ≥ 12** — the RTP header size. Shorter = malformed, discard.
2. **RTP version = 2** — the top two bits of byte 0 must be `0b10`. Else discard.
3. **Payload type = 96** — the low seven bits of byte 1. Mismatch = another stream, discard.
4. **Source IP = the configured server IP**. Any other address is dropped. This is a
   whitelist, not a hint: it is what stops a second device on the LAN from injecting
   audio. `0` (no server saved) means accept anything.
5. **Payload length ≥ 1920 bytes** (one full 20 ms frame). Shorter is dropped, because
   a partial frame would shift every later sample.
6. **Sequence continuity**, against `last_seq`:
   - `seq == last_seq + 1` — in order, write the payload to the ring.
   - `seq == last_seq` — a duplicate, discard.
   - `seq > last_seq + 1` — a gap. Count the missing frames (capped at 64) and
     silence-fill them, bounded by the ring's free space so the fill can never be the
     reason a live packet is lost.
   - Anything else — treated as a gap of one frame.

### What is deliberately **not** checked

| Field | Why not |
|---|---|
| **Timestamp** (bytes 4–7) | Redundant with the sequence check: a sender that skips 960 per frame *is* the behaviour being verified, and a receiver comparing timestamps would add a second failure mode for no extra safety. The sender emits a correct, continuous timestamp (`docs/SETUP.md` documents it) and the receiver trusts the sequence number. |
| **SSRC** (bytes 8–11) | The sender picks a **random SSRC per process** and a new one on every seek or volume change. Pinning an SSRC would break every restart mid-session. |
| **Marker bit**, padding, extension | Constant in this design (`player.py` never sets them). A sender that set them would still be read correctly, because the payload is taken as a fixed 1920 bytes. |
| **Sample rate / channels** | Fixed by the protocol, not carried per-packet; the receiver always assumes 48 kHz mono. |

If the wire format ever changes, the receiver is the single place to change — see the
byte-order note below.

Never trust a UDP datagram. The worst case of a bad validation is silence for one frame
— acceptable. The worst case of trusting a bad datagram is corrupted audio.

## Jitter / ring buffer

The same PSRAM ring buffer from the TCP prototype is reused:

- Ring holds PCM 16-bit LE mono samples (raw PCM, after validation).
- RX task writes validated PCM into the ring (producer). Audio/pump task reads from the ring and feeds I2S (consumer).
- Ring sized for a comfortable jitter cushion (tested 65 KB in the TCP prototype).
- Pump is DMA-backpressure driven: writes a chunk to I2S, waits for I2S FIFO/threshold before the next chunk. No fixed vTaskDelay.

## Loss handling (UDP) — silence fill, never block

For TCP, no-drop + backpressure was correct. For UDP/RTP, delivery is not guaranteed. The production rule:

```
packet arrives
      ↓
sequence number checked
      ↓
missing packet?
  ┌────┴─────┐
  │          │
yes         no
  │          │
silence     PCM
  │          │
  └────┬─────┘
      ↓
jitter/ring buffer
      ↓
I2S DMA
```

- If a packet is missing (seq > expected), fill the missing samples with silence (zero PCM).
- The audio/I2S task is never blocked waiting for a missing UDP packet. It keeps pulling from the ring; if the ring empties, it plays zeros and continues.
- This avoids the "buzz/noise" that came from replaying stale buffer contents on drop (the TCP-drop bug).

## I2S byte order — le→c native

RTP L16 payload is little-endian 16-bit PCM (this project's chosen wire format; the sender emits LE samples via `struct.pack("<h")`). The ESP32-S3 is also little-endian, and the I2S driver (`I2S_STD_PHILIPS_SLOT` with `I2S_DATA_BIT_WIDTH_16BIT`) reads native `int16_t` values and serializes each sample MSB-first on BCLK. So the LE RTP payload can be blitcopied directly into the I2S write buffer as `int16_t` — no byte swap is needed on this platform.

The receiver writes the validated RTP PCM payload straight into the ring buffer as `int16_t`, then the audio pump duplicates each sample into L+R stereo slots for the I2S driver. If the sender format ever changes (e.g. to big-endian RTP L16), the receiver is the single place to add a conversion.

## WiFi / network modes

### Setup AP mode (first boot, factory reset, or after WiFi failure)

- SoftAP: SSID `AudioNode-Setup`, open (no AP password).
- The board runs an HTTP server on the AP subnet (192.168.4.1) serving the setup page.
- The page is reachable by navigating to the board's AP IP in a browser; on most phones connecting to the open AP triggers an automatic portal prompt.
- In this mode the UDP listener is already bound (`0.0.0.0:1234`) but nothing streams; the board waits for the user to submit the config form.

### STA mode (normal operation)

- The board connects to the configured WiFi (SSID + password from NVS).
- On successful association + got IP: the UDP RTP listener starts on port 1234, the LED goes blue (breathing = waiting for server), then to VU when packets arrive.
- If association fails or no IP within ~30 s: revert to setup AP mode (so a changed router doesn't brick the board). NVS config is kept — the user retries with the same or edited SSID.
- If WiFi later drops: LED goes red; the board keeps reconnecting. On reconnection it resumes listening. No factory reset.

### Factory reset

- Trigger: hold BOOT button (GPIO0) for ~5 seconds after normal boot.
- Effect: erase the NVS configuration partition (WiFi SSID/password, server IP/port) → reboot.
- After reboot: board is in setup AP mode with default (empty) config.
- Short GPIO0 presses during normal operation are ignored.
- Temporary WiFi loss does NOT erase NVS — only the explicit 5-second BOOT hold does.

## RGB LED states

| State | LED |
|---|---|
| WiFi down / not connected | Solid dim red |
| WiFi connected, waiting for RTP server | Blue breathing (fade in/out ~3 s) |
| Streaming audio | VU meter — green (quiet) → yellow → red (loud), pulsing with level |

"Streaming" is decided by **packet recency**, not a sticky flag: the LED stays on the VU only while RTP packets keep arriving. A gap longer than ~200 ms means the stream ended, and the LED returns to blue breathing (waiting).

## Multi-node

Unicast first (production initial):

```
                 ┌──► ESP32 #1 :1234
                 │
Python RTP ──────┼──► ESP32 #2 :1234
sender           │
                 ├──► ESP32 #3 :1234
                 │
                 └──► ESP32 #N :1234
```

The sender sends the same RTP stream to each board IP:port. Each board validates and plays independently. Multicast (239.x) is a future option — not in v1 because AP/router multicast behavior varies.

## Archive note — TCP prototype

The first transport was raw PCM over TCP (milestones M0–M3). It is in neither this
tree nor the current docs: the full history is in git, and the audio pipeline it
proved (I2S, PSRAM ring, DMA-backpressure pump, ×2 gain, RGB LED) is the one still
running. Only the transport changed — TCP → UDP + RTP.