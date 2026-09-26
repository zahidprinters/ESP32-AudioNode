# System Patterns

## Architecture

```
PC (browser) ──HTTP──> Flask/Socket.IO server ──RTP L16/UDP──WiFi──> ESP32-S3
                          │                                        │
                    music folder, config                  I2S ──> MAX98357A ──> speaker
                    JSON config store                     WS2812 LED (state)
```

Two independent halves that meet at one wire format:

- **Firmware** (`firmware/main/main.c`) — Wi-Fi STA, setup AP + HTTP portal,
  NVS config, RTP/UDP receiver, PSRAM ring buffer, I2S pump, LED, factory reset.
- **Server** (`audio_player/`) — Flask + Socket.IO web app, library scan,
  RTP pacing and filter chain, JSON config persistence, LAN discovery.

## Design decisions

- **2026-09 — RTP L16 over raw PCM, no compression.** Keeps latency low and
  firmware simple; a compressed format would require an audio decoder on the
  ESP32, which the PSRAM and CPU budget do not justify for a LAN use case.
- **2026-09 — Provisioning over an open AP, not a bundled app.** Two minutes
  from a bare board to playing audio, with no app store and no account.
- **2026-09 — Factory reset erases NVS; a Wi-Fi drop does not.** A board that
  loses the network must come back on its own, not return to setup.
- **2026-09 — No back-channel from the board.** Deliberate simplification. The
  cost is that the UI can only claim "the server is sending", never "the
  speaker is audible". This is why the README says so explicitly.

## Patterns in use
- **Paced streaming** — `player.py` paces RTP frames to the 20 ms frame time
  rather than blasting the socket.
- **Write-then-replace persistence** — `config.py` writes a new file and
  replaces the old, so a crash mid-write cannot truncate the config.
- **Dependency verification on every start** — first-run failures are guided and
  logged rather than surfacing as an import error (commit `51219e7`).
- **No test framework** — `selftest.py` is hand-rolled and exits non-zero on
  failure, which is all this project needs.

## Critical paths
- `firmware/main/main.c` — the board does nothing without this file working.
- `audio_player/player.py` — the pacing loop. A bug here is audible as
  stutter, not a crash.
- The RTP frame size constant (960 samples) — changing it silently desyncs the
  I2S pump and the LED VU meter.

## Component relationships
- `player.py` depends on `config.py` for EQ presets and node settings.
- `app.py` depends on `library.py` for the music folder and on `player.py` for
  transport.
- `selftest.py` exercises `player.py` and `config.py` without hardware.
