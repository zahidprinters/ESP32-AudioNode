# Architecture — AudioNode WiFi speaker box

## Product concept

A configurable, networkable speaker: an ESP32-S3 board with a MAX98357A class-D amp, plus an onboard WS2812 RGB LED. Drop it on any WiFi, point it at a server, and it plays PCM audio over RTP/UDP. Multiple boards can share one server stream.

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

The board's UDP RX task validates each datagram before feeding it to the ring buffer. A datagram that fails any check is discarded (silence-filled) and counted.

Checks, in order:

1. **UDP length ≥ RTP header** (≥ 12 bytes). Too short = malformed, discard.
2. **RTP version = 2**. The top 2 bits of byte 0 must be 0b10. Else discard.
3. **Payload type = 96**. Mismatch = wrong stream, discard.
4. **Payload length** is a multiple of 2 bytes (16-bit samples) and within the expected frame-size window (≈ 1 920 bytes). Too small/large = discard.
5. **Source IP = configured server IP**. Packets from any other IP are ignored.
6. **Sequence + timestamp sanity**.
   - Expected next seq = last_seq + 1.
   - seq < expected → old/reordered packet, discard.
   - seq > expected → gap (missed frames); fill silence, count the gap.
   - Timestamp should advance by 960 per seq step. A backwards timestamp or one inconsistent with the sequence = discard.

Never trust a UDP datagram. The worst case of a bad validation is silence for one frame — acceptable. The worst case of trusting a bad datagram is corrupted audio.

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
- The board runs an HTTP server on the AP subnet (e.g. 192.168.4.1) serving the setup page.
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

The TCP implementation (raw PCM over TCP, M0–M3) is archived, not deleted:
- Git history retains all TCP commits.
- PROJECT_STATE.md records the verified TCP milestones.
- The audio pipeline is preserved and reused in the RTP build.
- The transport layer is replaced (TCP → UDP + RTP).

The TCP path proved the audio hardware works end to end. The RTP path is the product transport.