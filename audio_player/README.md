# audio_player — the PC server

The PC half of AudioNode. It decodes audio with ffmpeg, slices it into 20 ms RTP
frames and streams them over UDP to one or more boards. A single-page web UI drives
it; the same operations are exposed as REST and Socket.IO for scripted clients.

```
audio file ──ffmpeg──▶ s16le 48 kHz mono ──▶ 20 ms RTP L16 frames ──UDP──▶ board :1234
```

## Install

```powershell
pip install -e .                          # from the repository root
# or, without packaging:
pip install -r requirements.txt
```

Python 3.11 or newer. ffmpeg does **not** need to be on `PATH` — `imageio-ffmpeg`
supplies a static binary. The optional `PyAudioWPatch` is only for the CLI's Windows
loopback mode (`pip install -e ".[windows_loopback]"`).

## Run

```powershell
python -m audio_player.app               # UI at http://localhost:5000
audio-player                             # same thing, when installed
```

### On Windows: click and go

Double-click **`start_audioplayer.bat`**. It picks a Python interpreter, checks it has
what the server needs, starts the server, and opens the UI in your browser. Leave the
window open while you listen; **stop it with Ctrl+C in that window**, or just close the
window — either way the server shuts down and releases the port.

If the Python it finds does not have the server's packages, it says so in one line and
gives you the exact command to fix it, rather than failing with a traceback. A `.venv`
in the repository root is preferred when present, which makes the choice deterministic.

To have it start by itself at logon (or at boot with `-AtStartup`), run
`install_startup.ps1`; `uninstall_startup.ps1` removes that task again. The task starts
the server quietly, without opening a browser.

| Flag | Meaning |
|---|---|
| `--host` | HTTP bind address (default `0.0.0.0`) |
| `--port` | HTTP port (default 5000) |
| `--library` | initial media folder; the UI can change it later |
| `--node IP[:PORT]` | replace the node list; repeatable, default port 1234 |
| `--install-deps` | install the required packages into this interpreter, then exit |

## First run on a new machine

The required packages are **Flask, Flask-SocketIO and imageio-ffmpeg**; `simple-websocket`
is optional (without it Socket.IO falls back to long polling). `numpy` and
`PyAudioWPatch` are only needed for the Windows loopback mode of the CLI sender.

Every entry point — the launcher, `python -m audio_player.app`, the `audio-player`
script — verifies this before doing anything else, using the one list in `deps.py`:

- **All present** → it starts, and records the interpreter and package versions in
  [`logs/app.log`](../logs/README.md).
- **Something missing** → it does not start. Instead of a traceback you get the missing
  names, the exact command to fix it, and a note if only an optional one is absent. The
  same outcome is written to `logs/app.log`, so a failed first start is still a record.
- **The Windows launcher** additionally walks the interpreters it can find and picks the
  first one that can import them, because `python` on `PATH` is not the same interpreter
  in every shell — a tool's venv can shadow the real one.

To let the server install them for you, into that exact interpreter:

```powershell
python -m audio_player.app --install-deps
```

That is deliberately **opt-in, never automatic**: silently `pip install`-ing into
whatever `python` resolves to could modify a system install or another tool's virtual
environment. The command is always shown to the user, never run behind their back.

`selftest.py` asserts that `deps.py`, `requirements.txt` and `pyproject.toml` declare the
same set, so the list cannot drift into claiming packages the app never imports.


A board's address must be the **real current LAN IP of the board**, and the board's
saved Server IP must be the **real current LAN IP of this PC**. Discovery
(`Find boards on WiFi`) sweeps the local /24 and keeps Espressif MACs; typing the IP
by hand is the supported fallback. `192.168.1.50` in the UI placeholder is an example,
not a default that works.

## State and security

State lives next to the source, all git-ignored: `nodes.json`, `eq_presets.json`,
`settings.json` and the `media/` library folder (created on first import). A source
checkout therefore needs write access to its own directory.

**This server has no authentication and is not hardened.** It binds `0.0.0.0`, accepts
any origin, and runs Flask-SocketIO's Werkzeug development server. It is meant for a
trusted home LAN. Do not port-forward it, expose it to the internet, or run it on a
shared network. Anyone who can reach the port can play audio on your speakers and point
the app at any folder on the machine. Put a real WSGI server and authentication in front
of it before doing anything else with it.

## Module map

| File | Role |
|---|---|
| `deps.py` | the dependency list and its verification: what is required, what is optional, the exact install command, and the log line written on every start |
| `app.py` | Flask + Flask-SocketIO server: REST routes, WebSocket handlers, 250 ms position loop, 1 s status tick, scheduler thread |
| `player.py` | the one and only ffmpeg → RTP L16/UDP pipeline (`rtp_header()`, `Player`): real-time pacing, filter chain, seek, pause/resume |
| `library.py` | recursive media-folder scan, durations and sizes via ffmpeg |
| `config.py` | every tunable (wire format, EQ bands and presets, calibration, node defaults, paths) plus the `node_*` / `eq_*` / `settings_*` persistence helpers |
| `send_pcm.py` | standalone bench sender — `tone`, `file`, `loop` — no browser needed |
| `selftest.py` | the runnable self-check (see below) |
| `templates/index.html`, `static/app.js`, `static/style.css` | the single-page UI |
| `start_audioplayer.bat` | Windows one-click launcher: resolves a Python, verifies the packages, starts the server, opens the UI, and stops cleanly on Ctrl+C or window close. `/min` starts quietly with no browser (used by the logon task) |
| `install_startup.ps1` / `uninstall_startup.ps1` | register / remove a Windows scheduled task so the server starts at logon (add `-AtStartup` for boot, which needs admin) |
| `media/`, `nodes.json`, `eq_presets.json`, `settings.json` | runtime user state, git-ignored |

## REST API

| Method | Route | Body / query | Purpose |
|---|---|---|---|
| `GET` | `/` | — | the web UI |
| `GET` | `/api/status` | — | state, source, volume, position, nodes, EQ |
| `GET` | `/api/library` | `?root=` | scan a folder for audio files |
| `POST` | `/api/play` | `{path, volume?}` | start, or resume if paused on the same file |
| `POST` | `/api/stop` | — | stop and flush the stream |
| `POST` | `/api/pause` | — | stop the pipeline, keep the position |
| `POST` | `/api/resume` | — | continue from the paused position |
| `POST` | `/api/volume` | `{volume}` | 0.0 – 1.0 by default (ceiling: `max_volume`) |
| `POST` | `/api/seek` | `{position_ms}` | seek; restarts the pipeline at that sample |
| `GET` | `/api/eq` | — | current EQ state, band limits, preset names |
| `POST` | `/api/eq` | `{enabled, preamp_db, gains[10]}` | apply live; values are clamped, band count is validated |
| `POST` | `/api/eq/preset` | `{name}` | apply a built-in or user preset |
| `POST` | `/api/eq/presets` | `{name}` | save the current curve under a name |
| `GET` | `/api/settings` | — | max volume, default preset, default library root |
| `POST` | `/api/settings` | any subset of the above | change and persist |
| `GET` | `/api/schedule` | — | scheduled play/stop plans |
| `POST` | `/api/schedule` | `{name, action: play\|stop, file, time: "HH:MM"}` | add a plan (validated) |
| `DELETE` | `/api/schedule/<id>` | — | remove a plan |
| `GET` | `/api/nodes` | — | configured boards |
| `POST` | `/api/nodes` | `{ip, port?, name?}` | add or update a board |
| `POST` | `/api/nodes/remove` | `{ip}` | remove a board (the last one is kept) |
| `POST` | `/api/nodes/discover` | — | sweep the LAN for Espressif MACs |

Errors come back as `{"error": "..."}` with a 4xx status. Bodies that are not JSON are
treated as empty, so a bad request is a 400 rather than a 500.

## Socket.IO

Client → server: `play`, `stop`, `set_volume`, `seek`, `set_library_root`,
`get_status`.
Server → client: `player_status` (state, position, per-node position, EQ — pushed on a
250 ms loop and a 1 s tick so a freshly connected client self-heals), `library_updated`,
`schedule_updated`, `error`.

## Equalizer

A 10-band peaking EQ on VLC's centres — 60, 170, 310, 600, 1000, 3000, 6000, 12000,
14000, 16000 Hz — plus a preamp, both ±12 dB. Ten built-in presets ship with the app;
your own curves are saved to `eq_presets.json` and cannot overwrite a built-in.
Changes apply live by restarting the pipeline at the current position, so a small tick
is expected.

The ffmpeg chain, in order:

```
highpass (speaker guard) → low shelf (bass trim) → preamp → equalizer ×N
  → compressor → volume → limiter (0.5 ceiling)   ← always last
```

The limiter is last on purpose: the board applies a fixed ×2 digital gain, so a 0.5
ceiling means the DAC cannot be driven into clipping at any volume or EQ setting.
`selftest.py` asserts the ordering.

## Self-check

```powershell
python -m audio_player.selftest
```

No test framework. It asserts the RTP header and frame math the firmware validates,
measures the real send rate over a loopback UDP socket (catching the free-running
sender regression), checks that position survives pipeline restarts, verifies the EQ
chain invariants and preset round-trip, and confirms every element id used by
`app.js` exists in `index.html`. It exits non-zero on the first failure.

