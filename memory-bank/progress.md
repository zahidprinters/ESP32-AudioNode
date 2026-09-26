# Progress

Phase: DEV → TEST (feature-complete, awaiting packaging)

## Works

All verified **on hardware**, not inferred:

- **Boot tone** — 1 kHz through the MAX98357A; tone/noise ratio ~99x measured by
  PC-microphone recording.
- **Wi-Fi STA** — joins from NVS credentials, power-save off, gets an IP,
  RSSI −34…−41 dBm.
- **Setup AP** — empty NVS or a factory reset brings up `AudioNode-Setup` with
  the portal at 192.168.4.1; saving stores Wi-Fi, server IP, port and node name
  and reboots into STA.
- **Factory reset** — BOOT/GPIO0 held ~5 s erases NVS and returns to the setup
  AP. Wi-Fi drops never erase NVS.
- **RTP receive** — 48 kHz / 16-bit / mono / 20 ms frames, 821 packets over 20 s
  with zero drops, byte-exact against the sent frame count. Every datagram
  validated.

| Area | File | State |
|---|---|---|
| Board application | `firmware/main/main.c` | complete |
| RTP pipeline | `audio_player/player.py` | complete |
| Web app | `audio_player/app.py` + `static/` + `templates/` | complete |
| Library scan | `audio_player/library.py` | complete |
| Persistence | `audio_player/config.py` | complete |
| Bench sender | `audio_player/send_pcm.py` | complete |
| Self-check | `audio_player/selftest.py` | complete |
| Auto-start | `audio_player/install_startup.ps1` | complete |
| Packaging / installer | — | **not started** |

## Does not work

- **Multi-board clock synchronisation** — fan-out works, boards are not
  sample-aligned. Known and documented, not a defect being tracked to zero.

## Milestones
| Date | Milestone | Notes |
|---|---|---|
| 2026-09-25 | Design-system UI rebuild | dark + light, accessibility pass |
| 2026-09-25 | One-click startup fix | `start_audioplayer.bat` verified on Windows |
| 2026-09-26 | Memory bank added | this structure, repo clean |

## Known issues
- 3 commit identities exist in history; 2 are fabricated placeholders
  (`dev@esp32-audio-node.local`, `cline@audio-node.local`). History is left alone
  deliberately — see `~/.cline/rules/workflow.md`, "Author & License". Going forward,
  commits are `Nadeem <zahid_printers@yahoo.com>`.
