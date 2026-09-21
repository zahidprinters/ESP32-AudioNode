# tools/

Environment and setup tooling. Everything needed to go from a clean machine to
a running system lives here or is documented from here.

## `env.ps1` — ESP-IDF environment (Windows / PowerShell)

The canonical entry point. It exports `IDF_PATH`, the Xtensa toolchain, the
Python virtual environment, `CCACHE` and `ESP_IDF_VERSION`, mirroring the
official EIM profile (`C:\Espressif\tools\Microsoft.v6.1.PowerShell_profile.ps1`).

> Do **not** use `export.bat` from the IDF tree — the EIM install layout is
> different and it fails.

```powershell
# from the repository root
. tools\env.ps1
```

`env.ps1` reads the IDF version and tool paths from the EIM installation, so if
you installed IDF somewhere other than `D:\esp32\v6.1\esp-idf` /
`C:\Espressif\tools`, edit the `$IdfRoot` / `$ToolsRoot` values at the top of the
script.

### Verify the environment

```powershell
. tools\env.ps1
idf.py --version      # should print the same version as $env:ESP_IDF_VERSION
```

## Firmware: build, flash, monitor

```powershell
. tools\env.ps1
cd firmware
idf.py set-target esp32s3      # once per clean checkout
idf.py build                   # -> build/esp32_audio_node.bin
idf.py -p COM5 flash
idf.py -p COM5 monitor --no-reset
```

Board quirks (documented because they cost hours):

| Symptom | Fix |
|---|---|
| Flash cannot connect | Hold **BOOT**, tap **RESET**, release BOOT, retry |
| `waiting for download` in the log | Unplug/replug USB (no buttons needed) |
| USB-CDC console dies after flashing | Unplug/replug USB |
| Monitor will not attach | `python -m esptool --chip esp32s3 -p COM5 run`, then `idf.py -p COM5 monitor --no-reset` |

## Player app: setup and run

```powershell
# from the repository root — no ESP-IDF environment needed
python -m pip install -r requirements.txt
python -m audio_player.selftest        # verifies wire format + UI wiring
python -m audio_player.app             # UI on http://localhost:5000
```

ffmpeg is bundled through `imageio-ffmpeg`; no separate install step.

## Checks (run before every commit)

```powershell
python -m audio_player.selftest        # all checks must print OK
python -m compileall -q audio_player   # exit code 0
```

## References

* `docs/SETUP.md` — end-to-end first-time setup, provisioning, troubleshooting
* `docs/HARDWARE.md` — wiring, pins, power
* `CONTRIBUTING.md` — build/flash/test loop, commit policy
* `firmware/README.md` · `audio_player/README.md` — component detail