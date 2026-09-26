# firmware — ESP32-S3 AudioNode

ESP-IDF firmware for the speaker node. It joins Wi-Fi, runs a UDP listener on
port 1234, validates incoming RTP L16 datagrams, buffers them in PSRAM and pumps
48 kHz / 16-bit mono PCM into I2S at a MAX98357A amplifier. If no credential is
stored it boots a setup access point instead.

## Hardware

Board: **ESP32-S3-DevKitC-1-N8R2** (8 MB flash, 8 MB octal PSRAM) —
PSRAM is used for the jitter buffer, so it is not optional.

| MAX98357A | ESP32-S3 | Note |
|---|---|---|
| BCLK | GPIO 4 | I2S bit clock |
| LRC | GPIO 5 | I2S word select |
| DIN | GPIO 6 | I2S data |
| SD | GPIO 15 | driven HIGH = amplifier enabled |
| VIN | 5 V | |
| GND | GND | tie grounds if the amp has its own supply |

Onboard: **GPIO 48** = status RGB LED, **GPIO 0** = BOOT button (factory reset).

The amplifier needs no MCLK and derives its clock from BCLK. With SD at VDD it
runs at its 3 dB minimum gain, which is why the firmware applies a fixed **×2
(+6 dB) digital gain**; the sender compensates with a 0.5-ceiling limiter so that
gain can never saturate.

## Build and flash

ESP-IDF v6.1 is assumed. On Windows this repository ships `env.ps1` at the root,
which sets `IDF_PATH`, the toolchain and the Python venv:

```powershell
. tools\env.ps1                  # from the repository root
cd firmware
idf.py set-target esp32s3        # first time only
idf.py build
idf.py -p COM5 flash
idf.py -p COM5 monitor --no-reset
```

Notes:

- Replace `COM5` with your port. Never flash the Intel AMT serial port.
- If flashing cannot connect: hold **BOOT**, tap **RESET**, release **BOOT**.
- If the USB console dies after flashing, unplug/replug the board.
- Exit the monitor with `Ctrl+]`.

## First boot and configuration

1. Power on with no stored credential → the board starts the **open** setup AP
   `AudioNode-Setup`.
2. Connect to it and open <http://192.168.4.1/>.
   | Portal field | Stored as (NVS `node_cfg_t`) | Notes |
   |---|---|---|
   | Wi-Fi SSID | `ssid` | |
   | Wi-Fi password | `password` | |
   | Server IP (sending PC) | `server_ip` (+`has_server`) | source-IP whitelist for incoming datagrams |
   | Server port | `server_port` | the UDP listen port; blank/0 → **1234**. Validated 1–65535 before save. |
   | Node name | `node_name` | optional label, shown in the boot log and at `/debug`. |

   On save the board stores the blob in NVS, joins the network and listens on the
   configured UDP port (1234 by default). If it cannot connect within ~30 s it
   returns to the setup AP; the stored configuration is kept.

### Debug route

While the setup AP is up (no STA yet, or Wi-Fi down), the board serves
<http://192.168.4.1/debug> — a JSON snapshot of live state: `version`, `ssid`,
`server_ip`, `has_server`, `server_port`, `node_name`, `net_state`, `play_mode`,
`ring_used`, `ap_active`. Useful for sanity-checking that a save was applied
without needing serial.

### Pinout — fixed, not configurable

The hardware pinout is **hardcoded** in `main.c` (`#define`s) and is **not**
exposed through the setup portal:

|BCLK|LRC|DIN|SD|RGB LED|BOOT button|
|---|---|---|---|---|---|
|GPIO 4|GPIO 5|GPIO 6|GPIO 15|GPIO 48|GPIO 0|

GPIO 0 is a strap pin tied to the BOOT button (factory reset), and I2S signals
must land on valid I2S-capable GPIOs — a wrong assignment can silently brick
audio or the boot sequence. This firmware therefore targets exactly one board and
one pinout. Building for a different board means changing the `#define`s at the top
of `main.c` and accepting that nobody has verified the result on hardware.

Wi-Fi drops do not erase NVS — the board reconnects automatically and the LED
turns red meanwhile.

## Factory reset

Hold **BOOT (GPIO 0)** for ~5 s after power-on → NVS is erased and the board
reboots into the setup AP.

## Wire format

| Field | Value |
|---|---|
| Sample rate | 48000 Hz |
| Bit depth / channels | 16-bit / mono |
| Frame | 20 ms = 960 samples = 1920 bytes |
| Payload type | RTP/96 (L16, 48 kHz, mono) |
| Transport | RTP over UDP, listener port 1234 |
| Default silence | sent when frames are missing — the pump never blocks I2S |

Every datagram is validated (RTP version, payload type, **source IP against the
configured server**, payload size, sequence continuity — the timestamp and SSRC are
deliberately not checked; see [`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md)).
Loss is filled with silence rather than stalled, and the jitter buffer is flushed
when the stream ends so
audio stops promptly.

## Files

| Path | Role |
|---|---|
| `main/main.c` | the whole application: NVS config, Wi-Fi, setup portal, RTP/UDP receiver, jitter buffer, I2S pump, LED |
| `main/idf_component.yml` | managed component dependencies |
| `CMakeLists.txt`, `main/CMakeLists.txt` | ESP-IDF build glue |
| `sdkconfig.defaults`, `sdkconfig` | project defaults and the generated config |

## Verify the build

A successful build ends with `Project build complete`. The generated binary is
`firmware/build/audio_node.bin`. Build artefacts are git-ignored — never commit
`build/`, `managed_components/` or `sdkconfig.old`.

Behavioural verification is done on hardware (tone test, then a stream from
`audio_player`) and recorded in [`logs/`](../logs/).

## Component history

The root [`CHANGELOG.md`](../CHANGELOG.md) is the one canonical changelog for the
whole project. Current state and known limits: [`docs/PROJECT_STATE.md`](../docs/PROJECT_STATE.md).

## License

MIT — see the root [`LICENSE`](../LICENSE).
