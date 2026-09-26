# Function map

Every function in the project, what it is for, and what it returns. Use it to find the
right place to change something without reading both trees first. Line numbers are
approximate — they move when the file is edited; the names do not.

Three things meet here, and they share only the wire format:

```
audio_player/  ──RTP L16 / UDP──▶  board :1234  ──▶ PSRAM ring ──▶ I2S ──▶ MAX98357A ──▶ speaker
```

## Firmware — `firmware/main/main.c`

One file holds the whole board application. Top to bottom: audio format → ring buffer →
gain → NVS config → Wi-Fi events → STA mode → setup AP and portal → factory reset → I2S
and pump → LED → UDP receiver → `app_main`.

| Function | What it is for | Returns |
|---|---|---|
| `ring_used` | Bytes queued in the ring | `int` bytes (mutex held) |
| `ring_free` | Bytes still writable; one slot reserved so full ≠ empty | `int` bytes (mutex held) |
| `ring_write` | Producer side: copy PCM into the ring | bytes actually written — short only when full (backpressure) |
| `ring_read` | Consumer side: copy PCM out of the ring | bytes actually read — short when starved (an underrun) |
| `gain_clip` | Apply the ×2 digital gain, saturating instead of wrapping | one `int16_t` sample |
| `cfg_save` | Persist `node_cfg` to NVS as one versioned blob | `esp_err_t` |
| `cfg_load` | Load `node_cfg`; a stale or missing blob is *not* an error | `esp_err_t`; `ESP_ERR_NOT_FOUND` ⇒ raise the setup AP |
| `wifi_event_handler` | esp_event callback: start the STA connect, react to disconnects / lost IP, log AP station joins | — |
| `cfg_apply_server_whitelist` | Copy the configured server IP into the UDP source whitelist | — |
| `sta_mode_start` | Join the saved network, non-blocking | `esp_err_t` |
| `portal_get_handler` | `GET /` on the setup AP: send the provisioning form | `ESP_OK` |
| `url_decode` | Percent/plus-decode one form value | characters written |
| `valid_ipv4` | Strict dotted-quad check on user input | `1` valid, `0` not |
| `portal_save_handler` | `POST /save`: validate, store, reboot into STA. Bad input ⇒ HTTP 400, nothing saved | always `ESP_OK` |
| `debug_get_handler` | `GET /debug`: JSON snapshot of config + live state | `ESP_OK` |
| `register_debug_route` | Attach `/debug` to the setup AP's HTTP server | — |
| `setup_ap_start` | Raise the open setup AP + portal. First boot, factory reset, or STA failure | — |
| `failover_task` | Watchdog: no IP within 30 s ⇒ back to the setup AP, NVS kept | — |
| `factory_reset_task` | BOOT held 5 s ⇒ erase NVS and reboot; a short press is ignored | — |
| `rssi_task` | Log the associated AP's signal strength every 10 s | — |
| `i2s_init` | Configure I2S0: 48 kHz, 16-bit, Philips standard, no MCLK | — (aborts on failure) |
| `audio_pump_task` | The audio task: boot tone, or ring → gain → I2S, or silence. Paced by DMA backpressure only | — |
| `rgb_init` | Initialise the on-board WS2812 | — |
| `led_task` | Red = no Wi-Fi, blue breathing = waiting, VU meter = streaming | — |
| `udp_task` | The network task: bind UDP, validate each datagram, silence-fill gaps, write the ring | — |
| `app_main` | Entry point: config, Wi-Fi mode, then create every task | — |

### Task inventory (what may safely block what)

| Task | Must never | Why |
|---|---|---|
| `audio_pump_task` | block on the network, or sleep a fixed time | it is the audio clock; a fixed delay causes audible glitches |
| `udp_task` | block the pump | it only fills the ring |
| `led_task`, `rssi_task`, `failover_task`, `factory_reset_task` | spin or log unthrottled | USB-CDC `printf` floods starve the pump |

Cross-task hand-offs use `volatile` single-word flags. That is safe on Xtensa only; see
the note above the ring globals in `main.c`.


## Server — `audio_player/`

### `deps.py` — the dependency contract

| Function | What it is for | Returns |
|---|---|---|
| `log_path` | Where the startup log lives (`logs/app.log`) | `Path` |
| `append_log` | Append one timestamped line; never raises, never prints | `True` if written |
| `_imports` | Can this interpreter import that module? | `bool` |
| `missing` | Required distributions that will not import | `[(dist, module), …]` |
| `absent_optional` | Recommended-but-optional distributions not installed | `[(dist, module), …]` |
| `versions` | Installed version of each known distribution | `{dist: version \| None}` |
| `install_command` | The exact, quoted `pip install` command for this interpreter | `str` |
| `install` | Run that command (opt-in only, via `--install-deps`) | `True` if all present afterwards |
| `_block` | The user-facing "what is missing and how to fix it" text | `list[str]` |
| `ensure` | Verify before starting; log the outcome either way | `True` if the server can run |

### `config.py` — all tunables and all persisted state

| Function | What it is for | Returns |
|---|---|---|
| `Config.__init__` | Every default: wire format, EQ bands and presets, speaker calibration, node list, paths | — |
| `node_save` / `node_load` | Persist / restore the node list (`nodes.json`) | — / applies to `cfg` |
| `eq_save` / `eq_load` | Persist / restore the EQ curve and user presets (`eq_presets.json`) | — / applies to `cfg` |
| `settings_save` / `settings_load` | Persist / restore settings and schedules (`settings.json`) | — / applies to `cfg` |

All three pairs are write-then-replace, and a missing or corrupt file leaves the
defaults in place rather than raising.

### `player.py` — the one RTP pipeline

| Function | What it is for | Returns |
|---|---|---|
| `rtp_header` | 12-byte RTP header, V=2 / PT=96 | `bytes` |
| `Player.play` | Start streaming a file, or resume if paused on it | — (`FileNotFoundError` if absent) |
| `Player.stop` | Stop the stream and reset the counters | — |
| `Player.pause` / `resume` | Stop the pipeline but keep the position / continue from it | — |
| `Player.set_volume` | Set volume (restarts the pipeline at the current position) | — |
| `Player.seek` | Restart at a sample offset, keeping the position absolute | — |
| `Player.set_eq` | Clamp, persist and apply the EQ live | — (`ValueError` on a bad band count) |
| `Player.running` / `volume` / `sample_position` | Current state, volume, and position in samples | `bool` / `float` / `int` |
| `Player._af_chain` | Build the ffmpeg filter chain; **the limiter is always last** | `str` |
| `Player._start_pipeline_at` | Spawn ffmpeg and start the pump thread | — |
| `Player._kill_pipeline` | Tear down ffmpeg and the UDP socket | — |
| `Player._pump` | Thread: slice stdout into frames and send, paced to real time | — |
| `Player._send_frame` | RTP-wrap one frame, send to every node, sleep off the lead | — |
| `Player._eq_snapshot` | Copy of the EQ state for the status push | `dict` |
| `Player._status_cb` | Fire the status callback, swallowing UI errors | — |

### `app.py` — HTTP, WebSocket and scheduling

| Group | Functions |
|---|---|
| Setup | `create_app` (returns `app, socketio, player`), `_setup_file_log`, `main` |
| Status | `_nodes_for`, `_node_status`, `_status_snapshot`, `_on_player_status`, `background_position_loop`, `background_status_tick` |
| Transport (REST) | `index`, `api_status`, `api_library`, `api_play`, `api_stop`, `api_pause`, `api_resume`, `api_volume`, `api_seek` |
| Equalizer | `_eq_view`, `_preset_names`, `api_eq_get`, `api_eq_set`, `api_eq_apply_preset`, `api_eq_save_preset` |
| Settings and schedule | `api_settings_get`, `api_settings_set`, `_plans_from_body`, `api_schedule_get`, `api_schedule_add`, `api_schedule_remove`, `background_schedule_loop` |
| Nodes | `_local_net`, `_arp_entries`, `discover_nodes`, `api_nodes_get`, `api_nodes_add`, `api_nodes_remove`, `api_nodes_discover` |
| WebSocket | `ws_play`, `ws_stop`, `ws_volume`, `ws_seek`, `ws_set_library_root`, `ws_get_status` |

### `library.py`, `send_pcm.py`, `selftest.py`

| Function | What it is for | Returns |
|---|---|---|
| `scan_library` | Recursive audio-file scan with durations and sizes | `list[dict]` |
| `library._duration` | Parse `Duration:` out of an ffmpeg run | `float` seconds or `None` |
| `send_pcm.make_rtp_header` | 12-byte header, fixed SSRC (bench sender) | `bytes` |
| `send_pcm.make_tone_frame` | One 20 ms frame of sine, 16-bit LE mono | `bytes` |
| `send_pcm.tone_mode` | Stream a generated tone in real time | — |
| `send_pcm.file_mode` | Decode and stream a file in real time | — |
| `send_pcm.loop_mode` | Capture the Windows WASAPI loopback device and stream it | — |
| `selftest.check` | Record one check, printing OK or FAIL | — |
| `selftest.test_*` | The runnable checks: modules import, RTP header, frame math, pacing, position, EQ, dependencies, UI element-id contract, stylesheet coverage, config | — |
| `selftest.main` | Run every check; **exit 1 if any failed** | `int` exit code |

## Where to change what

| To change… | Go to |
|---|---|
| the wire format or receiver rules | `player.py` (send) **and** `main.c:udp_task` + `docs/ARCHITECTURE.md` (receive) |
| the sound of the speaker | the calibration values and built-in EQ presets in `config.py` |
| a filter in the chain | `player.py:_af_chain` — keep `alimiter` last |
| the UI | `templates/index.html` + `static/app.js`; element ids are checked by the self-test |
| a dependency | `deps.py` — then `requirements.txt` and `pyproject.toml`; the self-test fails if they disagree |
| where state is stored | `config.py` (`Config.__init__` paths) |
| a pin, or the audio format | the `#define`s at the top of `main.c` — hardware is fixed, not configurable |
