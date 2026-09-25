# WORKFLOW — mandatory for every session, every task

## Living memory

`docs/PROJECT_STATE.md` is the project's memory: what exists, what was verified,
what failed, what is decided. Read it before any change. Update it after any change.

## The loop

1. **Read** `docs/PROJECT_STATE.md`. Know what exists and what failed before.
2. **Minimal change.** One idea per build. Never batch untested changes.
3. **Compile** — `idf.py build` (firmware) and `python -m compileall -q audio_player` (app).
   On failure: record the verbatim error in `docs/PROJECT_STATE.md` §5, fix, rebuild.
4. **Flash + test** — `idf.py -p COM5 flash`, `idf.py -p COM5 monitor --no-reset`,
   then stream and listen. "It compiles" is not "it works".
5. **Log** — capture the session to `logs/<YYYY-MM-DD>_<milestone>.md` (git-ignored) and
   summarize the *conclusion* in `docs/PROJECT_STATE.md` §3 and `CHANGELOG.md`.
6. **Decide**:
   - Works → mark ✅ in §3, update §8, commit
     (`M<x>: <what works> (verified on hardware)` for firmware, `(verified)` for app).
   - Fails → do **not** commit. Record the error and the approach in §4/§5, then try a
     *different* approach. Never repeat a failed one.
7. **Update `docs/PROJECT_STATE.md`** with what changed, why, and the result. Every time,
   even for partial progress.

## Milestone order (never skip ahead)

serial tone → WiFi → RTP/UDP receiver → streaming. Audio is verified by ear and, when
needed, by PC-microphone recording (the boot tone measured a tone/noise ratio of ~99x).

## Clean-codebase rules

- **One canonical file per purpose.** No `test_2.py`, `sender_v2.py`, `main_copy.c`.
  Edit the existing file; variation belongs in arguments, not in new files.
- One sender CLI (`audio_player/send_pcm.py`), one firmware entry
  (`firmware/main/main.c`), one self-check (`audio_player/selftest.py`).
- Experiments and scratch live in `tmp/` (git-ignored, disposable). Never in the
  source tree.
- Abandoned files are **deleted**, not renamed or parked.
- Session logs go in `logs/`, one file per session, never scattered in source folders.
- Before creating any file: check `docs/PROJECT_STATE.md` §2 and `git status`; extend
  what exists instead of adding a parallel copy.

## Anti-patterns

- Re-trying a known-failed approach (check §4 first).
- Re-writing code that already exists (check the §2 feature map first).
- Batching many changes before one build.
- Committing unverified code.
- Letting the audio task wait on the network.
- Erasing NVS on Wi-Fi failure — only the 5-second BOOT hold erases config.
