# logs/

Local development logs. **Nothing in this folder is tracked by git** — see
`.gitignore` (`logs/*`, with this README kept via `!logs/README.md`).

## Why it is not committed

Raw test transcripts contain machine-specific and private data:

* private LAN addresses of the boards and the development PC
* the Wi-Fi SSID of the lab network
* serial-console dumps and process noise

Those are not needed to use the project and should not be published. Keep
captures local; commit only the *conclusions* to `CHANGELOG.md` and
`docs/PROJECT_STATE.md`.

## Convention

One file per session or milestone, named `YYYY-MM-DD_<milestone>.md`:

```
logs/2026-09-15_app-v1-live.md
```

A capture should say what was run, what was observed, and the raw evidence
(packet counters, timings, error text). If a test fails, log it — the failure
record is what stops the next session from repeating the attempt (see
`docs/PROJECT_STATE.md` §4).

## Capturing serial output

```powershell
. tools\env.ps1
cd firmware
idf.py -p COM5 monitor --no-reset | Tee-Object ..\logs\$(Get-Date -Format 'yyyy-MM-dd')_session.md
```

Delete finished logs freely — they are scratch, not history.