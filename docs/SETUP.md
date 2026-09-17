# Server setup — AudioNode

How to run the audio server that sends PCM audio to one or more AudioNode boards over RTP/UDP.

## Overview

The server reads audio (from a file, the PC's speaker output, or a generated tone), encodes it to RTP L16 (48 kHz / 16-bit / mono / 20 ms frames), and sends it via UDP to the board's IP on port 1234.

The **server side lives in `audio_player/`** and has two front ends:

| | Command | Use it for |
|---|---|---|
| **Browser app** (recommended) | `python -m audio_player.app` → http://localhost:5000 | Everyday use: pick a song from a folder, play/stop/seek/volume, see the live position |
| **CLI sender** | `python audio_player\send_pcm.py …` | Scripting, quick connectivity/tone tests, CI-ish checks |

Both drive the same ffmpeg → RTP L16 → UDP pipeline. VLC is documented as an alternative, but note that VLC does not have a clean GUI path for sending raw L16/RTP to a unicast IP — use `audio_player` for reliability.

## Browser app (recommended)

```powershell
cd d:\esp-idf
python -m audio_player.app            # UI at http://localhost:5000
```

Useful flags:

```powershell
python -m audio_player.app --library "D:\Music"
python -m audio_player.app --node <board-ip>:1234 --node 192.168.1.51:1234
python -m audio_player.app --port 8080
```

Then open http://localhost:5000 (use the literal IP `127.0.0.1` if `localhost` feels slow —
on Windows, `localhost` costs ~2 s per request in name resolution), point the library
box at your music folder, press Scan, pick a file, press Play.

Defaults (node IP/port, library root, volume) live in `audio_player/config.py`.

Run the built-in check any time with `python -m audio_player.selftest` — it validates the
RTP wire format, the frame math, the real send rate, position-across-restart, and the
UI's element-ID contract (29 asserts, no test framework).

## Prerequisites

- Python 3.8+
- ffmpeg (for file mode) — the `imageio-ffmpeg` pip package gives you a static ffmpeg binary with no system install
- numpy (for tone mode + some processing)
- On Windows only: `pyaudiowpatch` (PyAudio fork with WASAPI loopback) for capturing PC speaker output

## Install (all platforms)

```bash
pip install numpy imageio-ffmpeg
```

## Install (Windows only — for loopback / VLC-mirrored mode)

```powershell
pip install pyaudiowpatch
```

## Find the board's IP

After setup, the board joins your WiFi and its RGB LED breathes blue while waiting for the server. The IP is shown in the board's serial monitor after it connects:

```powershell
idf.py -p COM5 monitor --no-reset
# look for: got ip: 192.168.x.x
```

Or read it from the setup web page if the board shows it there.

## Usage (CLI sender)

Run from the repository root (`d:\esp-idf`):

```bash
python audio_player\send_pcm.py file  <path>  <board_ip> [port] [vol]
python audio_player\send_pcm.py loop  <board_ip> [port] [vol]
python audio_player\send_pcm.py tone  <board_ip> [port] [freq] [seconds] [vol]
```

Defaults: port = 1234, vol = 1.0.

### File mode (all platforms)

Decode an audio file (mp3, flac, wav, aac, etc.) via ffmpeg to 48 kHz / 16-bit / mono raw PCM and stream it as RTP in real time:

```bash
python audio_player\send_pcm.py file "D:\New folder\song.mp3" <board-ip>
python audio_player\send_pcm.py file "D:\New folder\song.mp3" <board-ip> 1234
```

Real-time pacing: the sender sleeps briefly after each frame so playback on the board matches real time (the board's jitter buffer won't underrun).

### Loop mode (Windows — mirror the PC speakers)

Capture whatever is playing through the PC's speakers via WASAPI loopback and stream it as RTP. VLC (or any media player) controls play/pause/volume on the PC; the board mirrors the PC speakers.

```powershell
python audio_player\send_pcm.py loop <board-ip>
```

### Loop mode (Mac / Linux)

On Mac and Linux, WASAPI loopback isn't available. Options:

- **Linux (PulseAudio)**: capture the monitor source with `parec` and pipe to the sender, or use a PulseAudio capture source as the input.
- **Mac**: use ffmpeg with avfoundation to capture output, or route through a virtual audio device.
- **Simplest cross-platform fallback**: use `file` mode — it works everywhere once ffmpeg is installed.

Loopback support for Mac/Linux is a future helper. For now those platforms use `file` or `tone`.

### Tone mode (all platforms)

Generate a sine tone at the given frequency and stream it as RTP. Useful for verifying connectivity, volume, and the RGB LED VU behavior:

```bash
python audio_player\send_pcm.py tone <board-ip> 1234 1000 30 0.5   # 30s of 1kHz @ 0.5
python audio_player\send_pcm.py tone <board-ip>                    # default: 1kHz, 30s, vol 0.5
```

## Volume / headroom

The sender applies a mild processing chain on the decode so the board's ×2 digital gain doesn't clip:

- High-pass ~150 Hz (removes rumble / DC offset)
- Bass reduction (the amp's 3 W bass peaks can dominate)
- Compressor / limiter
- Volume scaling (default 1.0)

Adjust the `vol` argument if the board is too loud or too quiet. If you hear distortion, reduce `vol` — don't just turn it up on the amp.

## Pacing

All submodes pace the send so audio on the board plays in real time. The sender tracks how much audio it's sent vs. wall-clock elapsed time and sleeps briefly if ahead. This keeps the board's jitter buffer from underrunning.

## VLC as an alternative server

VLC excels at **compressed** streaming (MP3, AAC) over HTTP or RTP/UDP. The board currently expects **raw RTP L16** (uncompressed PCM).

- VLC does not have a clean GUI path for sending raw L16/RTP to a unicast IP.
- For compressed streaming to work, the board would need an RTP depacketizer for the codec (MP3/AAC) — a future board enhancement.

So for the **current product**, use the Python sender. VLC is documented as a future path for compressed streaming (lower bandwidth, same low latency), not the primary setup.

If you want to experiment with VLC sending raw PCM/RTP today, it requires manual RTP payload configuration and is not plug-and-play — use the Python sender for reliability.

## Firewall

- The sender sends **UDP** to the board's IP on port **1234** (outbound from the server PC).
- Outbound UDP from the PC to the board is usually allowed by default. If the board doesn't receive anything, check:
  - Board IP is correct (re-read from monitor or setup page).
  - No local firewall rule blocking outbound UDP to that subnet.
  - The WiFi AP is not in AP-isolation / client-isolation mode (that prevents devices on the same AP from talking to each other). Disable AP isolation on the router, or use a different AP.

## Equalizer (browser app)

The UI has a VLC-style 10-band equalizer (60 Hz … 16 kHz) with a preamp slider.
Changes apply live while playing; the limiter stays last in the ffmpeg chain, so
the board can never clip no matter what the EQ does.

- **Enable** checkbox turns the EQ on/off. Off = the measured speaker-calibration
  chain (65 Hz highpass, −3 dB bass shelf @ 120 Hz, compressor, limiter).
- **Preset** dropdown: Flat, Acoustic, Bass Booster, Bass Reducer, Classical, Pop,
  Rock / Metal, Vocal / Voice, Treble Boost, Mid Cut (speaker) — the last one
  encodes this speaker's measured distortion zone (250 Hz–1 kHz,
  `logs/2026-09-15_tone-diagnosis.md`).
- **Save…** stores the current curve under a name of your choice, persisted in
  `audio_player/eq_presets.json` (git-ignored per-user state).

REST: `GET/POST /api/eq`, `POST /api/eq/preset` (apply by name), and
`POST /api/eq/presets` (save current as a named preset).

## Multi-node (many boards, one server)

With the browser app, pass several `--node` flags (or edit `cfg.nodes` in
`audio_player/config.py`) and every packet goes to each node — one stream, many
speakers:

```powershell
python -m audio_player.app --node <board-ip>:1234 --node 192.168.1.51:1234
```

With the CLI sender, run one instance per board:

```bash
python audio_player\send_pcm.py file song.mp3 <board-ip> 1234   # board #1
python audio_player\send_pcm.py file song.mp3 192.168.1.51 1234   # board #2
```

This is unicast (one packet per board; the app loops over the node list). Multicast
(239.x) would reduce server bandwidth but is a future enhancement — AP/router
multicast behavior varies.
