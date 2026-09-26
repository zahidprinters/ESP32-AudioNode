# Development guidelines

The engineering rules for AudioNode: how it is built, tested, and changed. Read
before touching either product. The agent-enforced version of the same rules lives
in [`.cline/rules/`](../.cline/README.md).

## Toolchain (this machine)

ESP-IDF **v6.1** at `D:\esp32\v6.1\esp-idf`, tools at `C:\Espressif\tools`. The EIM
install layout differs from a manual one, so `export.bat` does **not** work — use the
repository's profile:

```powershell
. tools\env.ps1
cd firmware
idf.py set-target esp32s3
idf.py build
idf.py -p COM5 flash
idf.py -p COM5 monitor --no-reset
```

**COM5 is the board** (USB Serial Device). Never use COM3 — that is the Intel AMT
motherboard port. The server side needs nothing but Python 3.11 and
`requirements.txt`; it does not need the ESP-IDF environment.

### Board quirks (documented because each one cost hours)

| Symptom | Fix |
|---|---|
| `idf.py flash` cannot connect | Hold **BOOT**, tap **RESET**, release BOOT, retry |
| Log shows `waiting for download` | Unplug/replug USB — no buttons needed |
| USB CDC console dies after flashing | Unplug/replug USB |
| Monitor will not attach | `python -m esptool --chip esp32s3 -p COM5 run`, then attach the monitor |
| Monitor attach resets the board anyway | Retry the attach until the boot section appears; cumulative counters restart from 0 |
| A fix appears not to work | Stale senders/monitors are still feeding the board. `taskkill /F /IM python.exe /T` before every test |

## Protocol rules

RTP L16 over UDP, 48 kHz / 16-bit / mono / 20 ms frames = 960 samples = 1920 bytes.

- RTP: version 2, PT 96, `seq` +1 per frame, `ts` +960 per frame (samples, not ms),
  SSRC random per sender.
- Destination: board IP :1234, or the port stored by the setup portal. The datagram's
  source IP must equal the board's configured server IP — a whitelist, not a hint.
- The receiver validates every datagram (length, version, PT, source IP, payload size,
  sequence continuity) before any PCM reaches the ring buffer. Invalid = discard and
  silence-fill. The timestamp and SSRC are deliberately not checked — see
  ARCHITECTURE.md for why.
- A missing packet is filled with silence. The audio task must never wait for it.

`sdkconfig.defaults` is load-bearing: frames are 1932 bytes, over the 1500-byte MTU, so
they arrive IP-fragmented. `CONFIG_LWIP_IP4_REASSEMBLY` and
`CONFIG_LWIP_IP_REASS_MAX_PBUFS=20` are not optional — without reassembly lwIP drops
them silently and the board never sees the frame.

## Audio pipeline rules

- I2S 48 kHz, 16-bit, Philips standard, no MCLK; BCLK 4 / LRC 5 / DIN 6 / SD 15.
- Jitter ring in octal PSRAM; the pump is DMA-backpressure driven. Never a fixed
  `vTaskDelay` in the pump — it produced periodic audible glitches.
- ×2 digital gain on the board (+6 dB) with the sender's limiter at a 0.5 ceiling, so
  no volume or EQ combination can saturate the DAC.
- RX and audio are separate tasks. The audio task never touches the network. Wi-Fi
  reconnects, LED updates, HTTP handlers and logging are throttled so they cannot
  starve the pump — USB CDC `printf` floods are a real cause of dropouts.
- The ring is flushed when a stream ends so silence starts promptly.

## Build / flash / test loop

1. `idf.py build` must succeed before flashing. Never flash a stale build.
2. Flash, then monitor with `--no-reset`.
3. Stream something — `python -m audio_player.app`, or
   `python audio_player\send_pcm.py tone <board-ip> 1234 30 1000 0.5`.
4. Listen. When something is subtle, record the speaker with the PC microphone and
   measure the tone against the noise floor (the boot tone measured ~99x).
5. Server-side changes: `python -m compileall -q audio_player`,
   `python -m audio_player.selftest`, `python -m pip check`.

Milestones are proved in order — serial tone → Wi-Fi → RTP receiver → streaming. Each
one before the next.

## Commit policy

- Commit only states that were actually verified: firmware must have been flashed and
  observed; the app must have been started and exercised.
- Subject line: `<type>: <what works> (verified)`, where type is one of `feat`,
  `fix`, `ui`, `docs`, `chore`. Put the hardware qualifier in the subject only when
  the change actually had it: `(verified on hardware)` for firmware, `(verified)`
  for everything else.
- The body states what changed, why, and what was run. A commit that only says
  "fixed it" is not acceptable history.
- A failed attempt is documented in [PROJECT_STATE](PROJECT_STATE.md) §4/§5, then a
  *different* approach is tried. Never commit a broken state to tidy the log.

## File hygiene

- One canonical file per purpose. `send_pcm.py` stays `send_pcm.py`; the application
  stays in `firmware/main/main.c`; the server stays in `audio_player/`.
- Experiments go in `tmp/` — git-ignored and disposable. Nothing experimental stays in
  the source tree.
- Session logs go in `logs/`, one file per session. They are local scratch and are
  never committed; conclusions go to `CHANGELOG.md` and `PROJECT_STATE.md`.
- Abandoned files are deleted, not renamed or parked. Before creating a file, check the
  feature map and extend what exists.

## Anti-patterns

- Re-trying an approach that already failed.
- Adding a parallel implementation of something that exists.
- Batching several changes into one untested build.
- Treating "it compiles" as "it works".
- Blocking the audio task on a missing UDP packet.
- Erasing NVS on Wi-Fi failure — only the 5-second BOOT hold erases configuration.
- Blitting network bytes into I2S without thinking about endianness. It is safe *here*
  only because RTP L16 is little-endian and the ESP32-S3 is little-endian; the receiver
  is the one place to change if that ever stops being true.

## Known ceilings (deliberate, documented)

| Ceiling | Why it is acceptable | Upgrade path |
|---|---|---|
| Multi-board is not sample-synchronised | Each board keeps its own clock | Shared RTP timestamp plus a per-node offset phase |
| Volume and EQ changes restart the ffmpeg pipeline | ffmpeg volume is an input filter | Decode once, scale in-process |
| MP3 seek is not sample-accurate | Fine for a seek bar | Maintain a per-file sample index |
| Library scan decodes each file to read its duration | imageio-ffmpeg ships no ffprobe | Cache durations on disk |
| Discovery is a ping sweep plus an ARP read | Bounded to the local /24, ~10 s | Have the board announce itself |
| The app runs the Werkzeug dev server | Trusted LAN only; unauthenticated and unhardened | Real WSGI server plus auth before exposing it |
| The board pinout is compiled in | Prevents a portal mistake from bricking I2S or boot | Per-pinout build variants |

## Repository layout

```
firmware/                 ESP-IDF project (target esp32s3)
  main/main.c             the entire board application
  main/idf_component.yml  led_strip dependency
  sdkconfig.defaults      PSRAM + IP reassembly (both required, see above)
  sdkconfig               generated — do not edit by hand
audio_player/             the PC server
  app.py                  Flask + Socket.IO: REST, WebSocket, scheduler
  deps.py                 the dependency list + its verification (single source)
  player.py               the single ffmpeg -> RTP L16/UDP pipeline
  library.py              folder scan + durations
  config.py               all tunables + user-state persistence
  selftest.py             the runnable check (`python -m audio_player.selftest`)
  send_pcm.py             CLI sender: tone / file / loopback
  install_startup.ps1     register a logon/startup task (Windows)
  uninstall_startup.ps1   remove it
  start_audioplayer.bat   one-click launcher (Windows): pick Python, verify the
                          packages, start, open the UI, stop on Ctrl+C
docs/                     ARCHITECTURE, FUNCTION_MAP, SETUP, GUIDELINES, PROJECT_STATE
tools/env.ps1             ESP-IDF environment for this machine
logs/                     git-ignored session scratch; also logs/app.log, written
                          by the server on every start (and on a blocked one)
tmp/                      git-ignored experiments
```

The two products share nothing but the wire format. Firmware code stays in
`firmware/`, app code stays in `audio_player/`.
