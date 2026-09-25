# ESP32 AudioNode

A Wi-Fi speaker you provision from a browser: ESP32-S3 speaker firmware, plus a
Python server that streams 48 kHz mono audio to it as RTP L16 over UDP.

## What it does

- **The board** — an ESP32-S3 with a MAX98357A I2S amplifier joins your Wi-Fi from
  credentials it stores itself, then waits for audio. The on-board WS2812 LED shows
  state: red = no Wi-Fi, blue breathing = waiting for a stream, VU meter = streaming.
- **Setup without an app** — on first boot, or after holding BOOT for five seconds,
  the board opens the `AudioNode-Setup` access point. A web page at
  <http://192.168.4.1> takes the Wi-Fi credentials, the server address, the port and
  an optional node name, and stores them in NVS. No phone app, no cloud account.
- **The server** — a Flask + Socket.IO web app: browse a music folder, play, stop,
  seek, volume, a 10-band equalizer with saved presets, node management, LAN
  discovery, and scheduled play/stop. One stream fans out to several boards.
- **Wire format** — RTP L16 over UDP: 48 kHz, 16-bit, mono, 20 ms frames
  (960 samples = 1920 bytes), payload type 96, sequence +1 and timestamp +960 per
  frame.

Streaming to a single board is verified on hardware. Multi-board fan-out works but is
**not** clock-synchronised between boards. "Connected" and "playing" in the UI mean
*the server is sending* — the board has no back-channel, so they are not proof of
audio at the speaker.

## Quick start (server)

Python 3.11 is the tested version. From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m audio_player.app
```

Open <http://localhost:5000>, point **Library** at a folder of audio, add the board
under **Nodes**, pick a track and press play. ffmpeg arrives with the
`imageio-ffmpeg` package; nothing needs to be installed system-wide.

The app keeps its state next to its source (`nodes.json`, `eq_presets.json`,
`settings.json`, `media/`) — all git-ignored — so a source checkout needs write
access to the repository folder.

## Provision a board

1. Build and flash the firmware (below).
2. First boot, or a factory reset: connect to the **`AudioNode-Setup`** Wi-Fi and open
   <http://192.168.4.1>.
3. Enter the Wi-Fi SSID/password, the **sending PC's LAN IPv4 address** as Server IP,
   port `1234`, and an optional node name. Save & Connect.
4. Find the board's IP in the serial log (`GOT IP: …`) or your router's DHCP list, and
   add it in **Nodes**. Discovery scans the LAN for Espressif MACs; typing the IP is
   the supported fallback.
5. The board's saved Server IP must match the PC running the app. A DHCP reservation
   for both is strongly recommended.

An already-provisioned board only needs its IP added in the app. Holding **BOOT** for
about five seconds erases the stored configuration and reopens the setup access point.

## Hardware

| MAX98357A | ESP32-S3 |
|-----------|----------|
| BCLK      | GPIO 4   |
| LRC       | GPIO 5   |
| DIN       | GPIO 6   |
| SD        | GPIO 15 (HIGH = amplifier enabled) |
| VIN       | 5 V      |
| GND       | GND      |

The speaker goes across **OUT+ / OUT−**, never to ground. Tie the grounds together if
the amplifier runs from its own supply. The pinout is fixed in the firmware: GPIO 48
is the RGB LED and GPIO 0 the BOOT button. The amplifier needs no MCLK and sits at its
minimum 3 dB gain, which is why the firmware applies a fixed ×2 digital gain and the
sender limits to a 0.5 ceiling so it can never clip. Check your board's actual
flash/PSRAM variant before building, and start listening at low volume.

## Build and flash the firmware

ESP-IDF v6.1, target `esp32s3`. Board: ESP32-S3-DevKitC-1-N8R2 (8 MB flash, 8 MB
octal PSRAM — the jitter buffer lives in PSRAM, so it is not optional).

```powershell
. tools\env.ps1                          # this machine's IDF v6.1 environment
cd firmware
idf.py set-target esp32s3
idf.py build
idf.py -p COM5 flash                     # your board's port
idf.py -p COM5 monitor --no-reset
```

`tools/env.ps1` is specific to the original Windows install; on another machine use
your own ESP-IDF environment.

## Checks

```powershell
python -m compileall -q audio_player     # syntax
python -m audio_player.selftest          # wire format, pacing, EQ, UI contract
python -m pip check
```

These do not replace listening to the speaker and reading the serial log.

## Repository layout

```
firmware/      ESP-IDF source for the board (main/main.c holds the whole application)
audio_player/  the PC server: web app, RTP pipeline, library scan, self-check
tools/         ESP-IDF environment helper for this machine
docs/          architecture, setup, development guidelines, project state
logs/          local session logs (git-ignored scratch)
```

Two independent products that meet only on the network: the board speaks RTP L16/UDP
and nothing else; the server speaks the same wire format through `player.py` for the
web app and `send_pcm.py` for the CLI. The two front ends have separate processing
chains — do not assume they are identical.

## Documentation

- [Architecture, wire format and packet validation](docs/ARCHITECTURE.md)
- [Server setup, CLI sender, equalizer, multi-node](docs/SETUP.md)
- [Development guidelines and build/flash/test loop](docs/GUIDELINES.md)
- [Project state: what is verified, what failed, what is next](docs/PROJECT_STATE.md)
- [Firmware detail and provisioning](firmware/README.md)
- [PC app: API reference](audio_player/README.md)
- [Change log](CHANGELOG.md)

Historical documents may contain machine-specific paths and RFC 1918 example
addresses. Do not commit real Wi-Fi credentials: the board stores them in NVS and the
app never needs them.

## License

MIT — see [LICENSE](LICENSE).
