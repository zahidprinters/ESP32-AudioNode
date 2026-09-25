# .cline — agent rules and tooling

Editor/agent configuration for this repository. **Not part of the shipped product:**
nothing here is needed to build the firmware, run the server or use the system, and
nothing here is referenced by the code.

| File | Purpose |
|---|---|
| [`rules/esp32-audio-node.md`](rules/esp32-audio-node.md) | Project facts: toolchain and paths, board and pinout, setup AP and NVS, wire format, proven findings, file map |
| [`rules/workflow.md`](rules/workflow.md) | Process: the read → minimal change → build → flash → test → log → commit loop, clean-codebase rules, anti-patterns |

Read both before touching the project, in that order: the rules say *how* to work,
the facts say *what is true*.

## How the two files relate to the human documentation

Nothing is duplicated on purpose, and the split is strict:

- **Process and toolchain** are stated once, in `rules/workflow.md`, and summarised for
  humans in [`docs/GUIDELINES.md`](../docs/GUIDELINES.md).
- **Project state** (what is verified, what failed, what is next) is stated once, in
  [`docs/PROJECT_STATE.md`](../docs/PROJECT_STATE.md) — the canonical location. The
  `workflow.md` section references (§3, §4, §5, §8) point at that file's headings.
- **Protocol and architecture** are stated once, in
  [`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md); the rules file only records the
  invariants that would silently break the board if forgotten.

If you change a rule, change it in the file that owns it and update the cross-reference.
If a rule and a document disagree, the document is wrong until proven otherwise.

## Conventions for these files

- One file, one purpose. No per-task or per-session rule files.
- Keep them short enough to read in full before every task.
- No secrets, no real LAN addresses, no commit hashes that will go stale.
