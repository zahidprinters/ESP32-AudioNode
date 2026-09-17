# audio_player — browser-based RTP/UDP audio server

The PC side of the project. It decodes audio files with ffmpeg, slices the PCM
into 20 ms RTP frames and streams them over UDP to one or more ESP32 AudioNode
boards. A single-page web UI in the browser drives it (library, transport,
10-band equalizer, node management), with a REST + Socket.IO API underneath for
scripted clients.

```
audio file ──ffmpeg──▶ s16le 48 kHz mono ──▶ 20 ms RTP L16 frames ──UDP──▶ board :1234
```

## Install

```bash
pip install -e .           # from the repository root
# or, without packaging:
pip install -r requirements.txt
```

Requires Python ≥ 3.11. ffmpeg itself is **not** required on `PATH` — it is
bundled by `imageio-ffmpeg`.

## Run

```bash
python -m audio_player.app                      # UI at http://localhost:5000
audio-player                                    # same, when installed
```

| Flag | Meaning |
|---|---|
| `--host` | HTTP bind address (default from `config.py`) |
| `--port` | HTTP port |
| `--library` | initial media folder (the UI can change it later) |
| `--node IP[:PORT]` | replace the node list; repeatable, default port `1234` |

Example — one board, a specific folder:

```bash
python -m audio_player.app --library "D:\Music" --node 192.168.1.50:1234
```

## Module map

| File | Role |
|---|---|
| `app.py` | Flask + Flask-SocketIO (eventlet) HTTP/WebSocket server, REST routes, Socket.IO commands, 250 ms status loop |
| `player.py` | the one and only ffmpeg → RTP-L16/UDP pipeline (`rtp_header()`, `Player`); real-time pacing, audio filter chain |
| `library.py` | folder scan plus ffprobe durations/sizes |
| `config.py` | every tunable (wire format, EQ bands, node defaults, paths) and the user-state helpers `eq_save()` / `eq_load()` |
| `send_pcm.py` | standalone RTP CLI sender (tone / file / loop) for bench tests without the web app |
| `selftest.py` | framework-free self-check — see below |
| `templates/index.html` | single-page UI: menubar, tabs (Library · Player · Equalizer · Nodes), footer status bar |
| `static/app.js`, `static/style.css` | UI logic and theme |
| `media/` | default library folder, created on import (git-ignored content) |
| `eq_presets.json`, `nodes.json` | runtime user state (git-ignored) |

## REST API

| Method | Route | Body / query | Purpose |
|---|---|---|---|
| `GET` | `/` | — | the web UI |
| `GET` | `/api/status` | — | state, source, volume, position, nodes, EQ |
| `GET` | `/api/library` | `?root=` | scan a folder for audio files |
| `POST` | `/api/play` | `{path, volume?}` | start (or restart at) a file |
| `POST` | `/api/stop` | — | stop and flush the stream |
| `POST` | `/api/volume` | `{volume}` | 0.0 – 1.0 |
| `POST` | `/api/seek` | `{position_ms}` | seek (restarts the pipeline) |
| `GET` | `/api/eq` | — | current EQ state |
| `POST` | `/api/eq` | `{enabled, preamp_db, gains[10]}` | apply EQ live |
| `POST` | `/api/eq/preset` | `{name}` | apply a saved built-in/user preset |
| `POST` | `/api/eq/presets` | `{name}` | save the current EQ curve under a name |
| `GET` | `/api/nodes` | — | configured boards |
| `POST` | `/api/nodes` | `{ip, port?, name?}` | add/update a board |
| `POST` | `/api/nodes/remove` | `{ip}` | remove a board |
| `POST` | `/api/nodes/discover` | `{subnet?}` | probe the LAN for boards |

## Socket.IO

Client → server: `play`, `stop`, `set_volume`, `seek`, `set_library_root`,
`get_status`. Server → client: `player_status` (state, position, per-node
position, EQ) and `library_updated`.

## Equalizer

VLC-style 10-band peaking EQ, ±12 dB per band plus a ±12 dB preamp:
**60 · 170 · 310 · 600 · 1000 · 3000 · 6000 · 12000 · 14000 · 16000 Hz**.
Built-in presets ship with the app; your own curves are saved to
`eq_presets.json`. Changes apply live (the pipeline restarts at the same
position, so a small tick is expected).

Filter chain (order matters):

```
highpass (sub-bass guard) → low shelf (bass trim) → preamp → equalizer ×N
  → compressor → limiter 0.5 ceiling  ← always last
```

The limiter is deliberately the final stage: the board applies a fixed ×2
digital gain, so a 0.5 ceiling guarantees it can never digitally clip, at any
volume or EQ setting. `selftest.py` asserts this ordering.

## Self-check

```bash
python -m audio_player.selftest
```

No test framework required. It asserts the RTP wire format and frame math,
sends real frames over a loopback UDP socket to check the pacing is real time,
verifies position survives pipeline restarts, validates the EQ chain invariants
(limiter last, clamping, preset round-trip), and checks that every element id
referenced by `app.js` exists in `index.html`.

## Known limitations

- MP3 seek is ffmpeg-dependent, not sample-accurate.
- Volume / EQ / seek changes restart the pipeline, which produces an audible
  tick while playing.
- The position update loop runs at 250 ms, so the seek bar is coarse.
- The UI shell is fixed-width for a single page; it stacks on narrow screens.

## Component history

Feature-by-feature history lives in the root [`CHANGELOG.md`](../CHANGELOG.md)
(one canonical changelog for the whole project). Verification runs are recorded
under [`logs/`](../logs/).

## License

MIT — see the root [`LICENSE`](../LICENSE).
