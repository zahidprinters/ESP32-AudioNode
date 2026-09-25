# Project state

Living memory of the project: what exists, what was verified, what failed, what is
decided, what is next. Updated after every change — see [GUIDELINES](GUIDELINES.md)
and [`.cline/rules/`](../.cline/README.md).

ESP32 AudioNode is a Wi-Fi speaker box. The board joins your network from stored
credentials and plays PCM sent to it as RTP L16 over UDP by a server on the same LAN.

## 1. Current focus

The system is feature-complete for its stated scope and verified on hardware. Nothing
is in flight. The open items are packaging and product decisions, in §8.

## 2. Feature map

| Area | File | State |
|---|---|---|
| Board application | `firmware/main/main.c` | complete — Wi-Fi, setup AP + portal, NVS config, RTP/UDP receiver, PSRAM ring, I2S pump, LED, factory reset |
| RTP pipeline | `audio_player/player.py` | complete — pacing, filter chain, seek, pause/resume |
| Web app | `audio_player/app.py` + `static/` + `templates/` | complete — library, transport, EQ, nodes, discovery, settings, schedule |
| Library scan | `audio_player/library.py` | complete — recursive scan, ffmpeg-derived duration |
| Persistence | `audio_player/config.py` | complete — nodes, EQ, settings and schedules (write-then-replace) |
| Bench sender | `audio_player/send_pcm.py` | complete — tone / file / loopback modes |
| Self-check | `audio_player/selftest.py` | complete — no framework, exits non-zero on failure |
| Auto-start | `audio_player/install_startup.ps1` | complete — Windows scheduled task, optional `-AtStartup` |
| Packaging / installer | — | **not started** (§8) |

## 3. Verified on hardware

- **Boot tone** — 1 kHz through the MAX98357A; tone/noise ratio ~99x by PC-microphone
  recording.
- **Wi-Fi STA** — joins from NVS credentials, power-save off, gets an IP, RSSI −34…−41 dBm.
- **Setup AP** — empty NVS, or a factory reset, brings up the open AP `AudioNode-Setup`
  with the portal at 192.168.4.1; saving stores Wi-Fi, server IP, port and node name
  and reboots into STA.
- **Factory reset** — BOOT/GPIO0 held ~5 s erases NVS and returns to the setup AP.
  Wi-Fi drops never erase NVS.
- **RTP receive** — 48 kHz / 16-bit / mono / 20 ms frames, 821 packets over 20 s with
  zero drops, byte-exact against the sent frame count. Every datagram validated
  (version, PT, length, source IP whitelist, seq/ts); losses are silence-filled and the
  pump never blocks.
- **Stream end** — the jitter buffer is flushed so audio stops promptly.
- **LED** — solid red (Wi-Fi down), blue breathing (waiting), green→yellow→red VU
  (streaming), decided by packet recency rather than a sticky flag.
- **App** — equalizer, play/stop/pause/seek/volume, position tracking, node management
  and scheduling exercised against a live board.

Under continuous load there are occasional 4–6 packet loss bursts in 2.4 GHz
conditions. They are silence-filled (an audible tick) and are RF variance, not a
regression. They are not fixed.

## 4. Tried, failed, rejected

Do not repeat these.

- **"No IP / no serial logs" was not a firmware bug.** A code review attributed it to
  four defects; checked on hardware the node was healthy — it had joined, got an IP and
  bound the socket. The node was silent because no sender was running. The diagnostics
  were kept anyway, so a real failure is no longer silent.
- **Bounded pacing broke the sender.** `0 < ahead < 0.1` looks like a safety net but
  disables pacing as soon as the sender runs 100 ms ahead, which happens immediately
  because ffmpeg hands the pump four frames per read. The sender free-ran at ~3x real
  time and the board logged drops. Correct form: sleep the whole lead, capped per
  iteration.
- **`server_port` stored but never consumed.** It was displayed and saved while the
  board always bound 1234. Deleted, then re-added only once it was validated and
  actually passed to `bind()`.

## 5. Errors and how they were fixed

| Symptom | Cause | Fix |
|---|---|---|
| `RuntimeError: The Werkzeug web server is not designed to run in production` | Flask-SocketIO rejects the bundled server by default | `allow_unsafe_werkzeug=True`; documented as a trusted-LAN dev server, not a deployment |
| Board plays nothing while the sender runs | The board whitelists the server IP and the saved address did not match the PC | Save the PC's current LAN IPv4; a DHCP reservation is recommended |
| Frames never reach the board | 1932-byte datagrams fragment and lwIP dropped them without reassembly | `CONFIG_LWIP_IP4_REASSEMBLY=y`, `CONFIG_LWIP_IP_REASS_MAX_PBUFS=20` |
| Periodic clicks during playback | A fixed `vTaskDelay` in the I2S pump | DMA-backpressure pump |
| Restarts lost nodes, EQ and settings | The state files were written but never loaded | Load all three at boot, before the routes are built |
| The UI froze on the first request after start | `_node_status()` was called while holding a non-reentrant lock | Snapshot under the lock, build the node view outside it |
| Board silent after a router change | — | A ~30 s station timeout returns to the setup AP, keeping NVS |

## 6. Decisions

- **D-1 RTP L16 over UDP**, not TCP: one datagram per 20 ms frame, no head-of-line
  blocking, silence-fill on loss.
- **D-2 The board is the listener.** The server sends to the board; the board never
  initiates. The configured server IP doubles as a source whitelist.
- **D-3 The config blob is versioned** (`CFG_VERSION`, currently 3). A board flashed
  with newer firmware rejects a stale blob once and re-provisions through the setup AP.
  Deleting `server_port` and later re-adding it both depended on this.
- **D-4 The pinout is compiled in**, not portal-configurable: GPIO 0 is a strap pin and
  I2S needs capable pins, so a portal mistake could brick boot or audio.
- **D-5 Unicast to each node**, not multicast: AP and router multicast behaviour
  varies and is not worth the failure modes on a home network.
- **D-6 The limiter is the last filter, ceiling 0.5**, because the board applies a
  fixed ×2 gain — the sender can never drive the DAC into clipping.
- **D-7 Multi-board is unsynchronised.** Frame-accurate sync is explicitly out of scope.

## 7. Known limits

- Pins are fixed: I2S 4/5/6, SD 15, RGB 48, BOOT 0.
- "Connected" / "playing" in the UI means the server is sending. The board has no
  back-channel, so it is not confirmation of audio.
- One node at a time from the browser UI, or one CLI instance per board; the app can
  also fan a single stream out to a node list, unsynchronised.
- No compressed streaming (MP3/AAC) board-side; the transport is raw L16.
- No packaged installer. Not started.

## 8. Next steps

Nothing is blocked. In rough order of value:

1. **Windows packaging** — service wrapper, Inno Setup installer, a prebuilt BIN for
   this board/amp/pinout, an in-app esptool flash panel. The app core above is the
   baseline it would wrap.
2. **Board-side confirmation** — a small back-channel so the UI can report that audio
   actually arrived, instead of inferring it from sending.
3. **Multi-board synchronisation**, if it is ever wanted (§6 D-7).
4. **The 2.4 GHz loss bursts** — raw UDP has no retry, so this means FEC or a
   transport change.

- **`int64_t` last-packet timestamp rejected.** It would be a torn read across two
  tasks; the existing `uint32_t` pattern is single-word atomic on Xtensa and
  wrap-correct.
- **A version byte alone does not gate stale NVS.** On this board a length check would
  also have rejected the old blob, but only the version byte catches a same-size
  reshuffle — both are required.
- **Attaching the monitor can reset the board** even with `--no-reset`; cumulative
  counters then appear to go backwards. Retry until the boot section appears.
