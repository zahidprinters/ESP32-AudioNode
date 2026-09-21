# WORKFLOW SYSTEM — MANDATORY (follow every session, every task)

## The system
`PROJECT_STATE.md` (workspace root) is the living memory of the project.
It tracks: current focus, feature map, verified working, tried-and-failed, error log, decisions, next steps.

## Mandatory loop (every task, no exceptions)
1. **READ** `PROJECT_STATE.md` before doing anything — know what exists, what failed before, what's next.
2. **MINIMAL CHANGE** — make the smallest possible change. One idea per build. Never batch multiple untested changes.
3. **COMPILE** (`idf.py build`) — if error: log verbatim in §5 of PROJECT_STATE.md, fix, rebuild.
4. **FLASH + TEST** (`idf.py -p COM5 flash`, `idf.py -p COM5 monitor --no-reset`) — observe on hardware.
5. **LOG EVERYTHING** — capture monitor output/errors into `logs/` (e.g. `logs/2026-09-08_M0-tone.md`) and summarize in PROJECT_STATE.md.
6. **EVALUATE**:
   - Works? → mark ✅ in PROJECT_STATE.md §3, update §8 next steps → **commit to git** (message: `M<x>: <what works> (verified on hardware)`).
   - Fails? → do NOT commit. Record exact error + approach in §4/§5. Try a DIFFERENT approach (never repeat a failed one).
7. **UPDATE PROJECT_STATE.md** with micro-level detail after every change — what, why, result. Every time. Even partial progress.

## Verification style
- Verify by ear + **PC microphone** recording/analysis when needed (proven: tone/noise ratio ~99x method).
- Prove each milestone before moving on: serial tone first → then WiFi → then RTP UDP receiver → then streaming.

## Anti-patterns (never do)
- Re-trying a known-failed approach (check §4 first)
- Re-writing code that already exists (check feature map first)
- Batching many changes before one build
- Committing unverified code
- "It compiles" = "it works" — hardware observation required

## CLEAN CODEBASE RULES (strict)
- **One canonical file per purpose.** Never create test_2.py, sender_v2.py, main_copy.c, etc. If a file needs changes, EDIT the existing file — never duplicate under a new name.
- **One test script** for the sender (`audio_player/send_pcm.py`), one main firmware entry (`firmware/main/main.c`). Variation happens via CLI arguments, not new files.
- **Experiments go in `tmp/`** (workspace root). Anything experimental, scratch, WIP, or disposable lives in `tmp/` — it is git-ignored and periodically deleted. Nothing experimental ever sits in the real code tree.
- Old/abandoned files are **deleted**, not renamed or left behind.
- Log files go in `logs/` (one file per session/milestone), never scattered in source folders.
- Before creating ANY new file: check §2 feature map + `git status` — if similar code exists, extend it instead.