# ESP32 AudioNode

A Wi-Fi audio streaming system with ESP32-S3 speaker firmware and a browser-based
Python player, featuring RTP/UDP streaming, node management, and a 10-band equalizer.

## Features

- ESP32-S3 + MAX98357A I2S speaker output, Wi-Fi setup portal, and saved configuration.
- Browser library selection, play/stop, seek, volume, and a 10-band EQ with saved presets.
- Player/Equalizer/Nodes tabs, node management and discovery assistance, Help/About.
- 48 kHz, 16-bit mono RTP/UDP audio, 20 ms frames, payload type 96.

Single-node streaming has been hardware-tested. Multi-destination sending exists,
but synchronized multi-speaker playback is not guaranteed or hardware-verified.
Discovery and sender status are not confirmation of audio reception by a board.

## Quick start (PC app)

Python 3.11 is the tested version. From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m audio_player.app
```

On Linux/macOS use `source .venv/bin/activate` instead. Open
**http://localhost:5000**, select your audio library folder, configure a node in
Nodes, select a track, and press Play. Media, EQ presets, and node settings stay
local and are excluded from Git. Optional Windows loopback capture requires
`python -m pip install PyAudioWPatch`.

`imageio-ffmpeg` provides ffmpeg. Source-checkout execution is recommended because
the app currently writes local state beside its source and needs write access.

## Connect a node

1. Build/flash the firmware with ESP-IDF, not Arduino.
2. On first boot connect to **AudioNode-Setup**, then open **http://192.168.4.1**.
3. Enter Wi-Fi credentials, the sending PC's LAN IPv4 address as Server IP, and
   port **1234**. Save & Connect, then reconnect your PC to the normal LAN.
4. Find the board's IP in the router's DHCP list or serial output. Add that IP
   and port 1234 in Nodes. Discovery is a convenience; manual entry is the fallback.
5. Remove or replace the example node address before playing. The board's saved
   server IP must match the sending PC. DHCP reservations are recommended.

An already-configured board only needs its IP added to the app. Holding BOOT for
about five seconds resets configuration and requires Wi-Fi provisioning again.

## Hardware / firmware

| MAX98357A | ESP32-S3 |
|---|---|
| BCLK | GPIO 4 |
| LRC | GPIO 5 |
| DIN | GPIO 6 |
| SD | GPIO 15 |
| VIN | 5 V |
| GND | GND |

Speaker goes across OUT+ and OUT-, not to ground. Share ground with any separate
amplifier supply. Check your board's actual flash/PSRAM variant before building.
Start listening at low volume.

From an activated ESP-IDF v6.1 shell:

```powershell
cd firmware
idf.py set-target esp32s3
idf.py build
idf.py -p COM5 flash
idf.py -p COM5 monitor --no-reset
```

Replace COM5 with your board's port. `tools/env.ps1` is specific to the original Windows
installation; use your own ESP-IDF environment on other machines.

## Checks

```powershell
python -m compileall -q audio_player
python -m audio_player.selftest
python -m pip check
```

These checks do not replace listening tests and serial observation on hardware.

## Documentation

- [Hardware overview and development history](docs/HARDWARE.md)
- [Architecture and wire format](docs/ARCHITECTURE.md)
- [Server setup, CLI sender, and EQ](docs/SETUP.md)
- [Development guidelines](docs/GUIDELINES.md)
- [Changelog](CHANGELOG.md)
- [Project state and outstanding verification](docs/PROJECT_STATE.md)
- [Firmware build notes](firmware/README.md)
- [PC app notes](audio_player/README.md)

`firmware/` is ESP-IDF source; `audio_player/` is the PC app; `logs/` contains
historical evidence; `tmp/` is ignored scratch space. Historical docs contain
machine-specific paths and private example addresses. The CLI and browser sender
have separate implementations; do not assume identical processing chains.

## Security and publication

Use on a **trusted LAN only**. The app has no authentication, accesses local files,
and binds to all interfaces by default. Do not port-forward it. For local-browser
access use `python -m audio_player.app --host 127.0.0.1`. RTP is unencrypted and
source-IP filtering is not cryptographic authentication. Discover only on your LAN.

The Wi-Fi **password was never committed**. The lab SSID and private LAN addresses
that appeared in working files and docs were replaced with placeholders, and the
whole Git history was rewritten and then verified to contain no Wi-Fi password or
SSID. That rewrite changed every commit hash, so cloned copies must be re-cloned.

Two exceptions to keep in mind: **private LAN addresses from the development network
still appear in historical docs and logs** (`CHANGELOG.md`,
`docs/PROJECT_STATE.md`, `logs/`), and **rotate your Wi-Fi password if it was ever
shared** — history scrubbing does not un-share a secret. Ignore rules never remove
secrets from previous commits, so keep `audio_player/nodes.json`, `eq_presets.json`,
and real media out of commits (all git-ignored by default).

## License

MIT — see [LICENSE](LICENSE). Dependencies retain their own licenses.
