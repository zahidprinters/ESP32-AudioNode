# ESP32 AudioNode — project facts (single source of truth)

Read this and [`workflow.md`](workflow.md) before any task. Process lives in
`workflow.md`; this file is only what is true about *this* project.

## Toolchain (this machine)

- **ESP-IDF v6.1** at `D:\esp32\v6.1\esp-idf`; tools at `C:\Espressif\tools`
  (EIM install — `export.bat` does **not** work, the layout differs).
- Environment: `. D:\esp-idf\tools\env.ps1` from the repo root.
- Build from `d:\esp-idf\firmware`:

  ```powershell
  idf.py set-target esp32s3
  idf.py build
  idf.py -p COM5 flash
  idf.py -p COM5 monitor --no-reset
  ```

- **COM5 = the board** (USB Serial Device). **COM3 = Intel AMT — never use it.**
- Quirk: the USB CDC console sometimes dies after flashing; unplug/replug USB fixes it.
  `waiting for download` → unplug/replug, no buttons. If the monitor will not attach:
  `python -m esptool --chip esp32s3 -p COM5 run`, then attach the monitor (sequentially —
  never both at once).
- A stale sender or monitor poisons every test. `taskkill /F /IM python.exe /T` first.

## Hardware

- Board: **ESP32-S3-DevKitC-1-N8R2** (8 MB flash, 8 MB octal PSRAM — the jitter ring
  lives in PSRAM, so it is not optional).
- Amp: **MAX98357A**, mono 3 W class-D, speaker on **OUT+/OUT−** (never to ground).
- No MCLK needed — the amp derives its clock. With SD at VDD it sits at minimum gain
  (3 dB), which is why the board applies **×2 digital gain** and the sender limits to a
  0.5 ceiling.

| MAX98357A | ESP32-S3 | | |
|---|---|---|---|
| BCLK | GPIO 4 | RGB LED | GPIO 48 |
| LRC | GPIO 5 | BOOT | GPIO 0 |
| DIN | GPIO 6 | | |
| SD | GPIO 15 (HIGH = enabled) | | |
| VIN | 5 V | | |
| GND | GND | | |

A separate 5 V supply for the amp **must** share ground with the board.

## Setup and configuration

- First boot or factory reset → open setup AP `AudioNode-Setup`, portal at
  <http://192.168.4.1> (also serves `/debug` as JSON while the AP is up).
- The portal stores Wi-Fi SSID/password, server IP, port (default 1234) and node name
  in NVS. The server IP is the source-IP whitelist for incoming datagrams.
- No IP within ~30 s → back to the setup AP, NVS kept. Reconnect the phone/PC to the
  real LAN afterwards.
- Factory reset: hold **BOOT** (GPIO 0) ~5 s after power-on → NVS erased → setup AP.
- **Wi-Fi loss never erases NVS**; the board retries and the LED goes red.
- The config blob is versioned (`CFG_VERSION` 3): newer firmware rejects a stale blob
  once and re-provisions.

## Audio and transport

- 48 000 Hz, 16-bit, **mono**, I2S Philips standard, no MCLK.
- **RTP L16 over UDP**, PT 96, 20 ms frames = 960 samples = 1920 bytes; `seq` +1 and
  `ts` +960 (samples) per frame; SSRC random per sender.
- **The board is the listener** (the server sends to it). Datagrams from any source IP
  other than the configured server are dropped.
- Validated per datagram: length, RTP version, PT, source IP, payload size, sequence
  continuity. Timestamp and SSRC are NOT checked, on purpose. Loss is silence-filled;
  the I2S task never waits for a packet.
- LED: red = Wi-Fi down, blue breathing = waiting, VU = streaming (by packet recency,
  not a sticky flag).

## Proven — do not re-litigate

- The MAX98357A needs no MCLK; SD HIGH = enabled; VIN on 5 V.
- The I2S pump must be DMA-backpressure driven, never a fixed sleep, never a spin.
- Wi-Fi power-save OFF. Jitter ring in PSRAM, flushed when a stream ends.
- Boot tone verified by PC microphone: tone/noise ratio ~99x.
- 1932-byte datagrams exceed the MTU, so `CONFIG_LWIP_IP4_REASSEMBLY` and
  `CONFIG_LWIP_IP_REASS_MAX_PBUFS=20` in `sdkconfig.defaults` are mandatory, not tuning.
- The board's saved server IP must equal the PC running the app.

## Credentials

Wi-Fi SSID/password are provisioned at runtime into NVS and are **never** committed.
Board IPs are DHCP-assigned — read them from the serial log, and prefer DHCP
reservations. Documentation uses placeholders (`<board-ip>`, `192.168.1.x`).

## Where things are

| Path | What |
|---|---|
| `firmware/main/main.c` | the whole board application |
| `firmware/sdkconfig.defaults` | PSRAM + IP reassembly (load-bearing) |
| `audio_player/player.py` | the one ffmpeg → RTP L16/UDP pipeline |
| `audio_player/app.py` | Flask + Socket.IO server and scheduler |
| `audio_player/selftest.py` | the runnable check — no test framework |
| `audio_player/send_pcm.py` | bench CLI sender (tone / file / loop) |
| `docs/PROJECT_STATE.md` | verified / failed / decided / next |
| `docs/ARCHITECTURE.md` | data flow, wire format, validation, LED, Wi-Fi modes |
| `docs/SETUP.md` | server setup, CLI usage, EQ, multi-node, firewall |
| `docs/GUIDELINES.md` | human development rules |
| `logs/` | git-ignored session scratch |
| `tmp/` | git-ignored experiments |
