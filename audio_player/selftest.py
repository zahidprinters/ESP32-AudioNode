# audio_player.selftest — one runnable check, no framework.
#
# Run:  python -m audio_player.selftest
#
# Covers the two things that break silently:
#   1. the RTP wire format the firmware validates (header bits + frame sizes)
#   2. the HTML/JS element-ID contract (a renamed id = dead UI, no error)

import os
import re
import sys
import time
import struct

from audio_player.config import (RTP_SRATE, RTP_PT, RTP_FRAME_MS,
                                 RTP_SAMPLES_PER_FRAME, RTP_BYTES_PER_FRAME,
                                 cfg)
from audio_player.player import rtp_header

HERE = os.path.dirname(os.path.abspath(__file__))
FAILS = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + ("  " + detail if detail else ""))
    if not cond:
        FAILS.append(name)


def test_rtp_header():
    print("RTP header (firmware requires v=2, PT=96, M=0):")
    h = rtp_header(seq=0x1234, ts=0xDEADBEEF, ssrc=0x0A0B0C0D)
    check("12 bytes", len(h) == 12, "got %d" % len(h))
    b0, b1, seq, ts, ssrc = struct.unpack("!BBHII", h)
    check("version=2", (b0 >> 6) == 2, "got %d" % (b0 >> 6))
    check("padding=0", (b0 >> 5) & 1 == 0)
    check("extension=0", (b0 >> 4) & 1 == 0)
    check("CSRC count=0", (b0 & 0x0F) == 0)
    check("marker=0", (b1 >> 7) == 0)
    check("PT=96", (b1 & 0x7F) == RTP_PT == 96, "got %d" % (b1 & 0x7F))
    check("seq round-trips", seq == 0x1234)
    check("timestamp round-trips", ts == 0xDEADBEEF)
    check("ssrc round-trips", ssrc == 0x0A0B0C0D)


def test_frame_math():
    print("Frame math (must match firmware ARCHITECTURE.md):")
    check("SRATE=48000", RTP_SRATE == 48000)
    check("frame_ms=20", RTP_FRAME_MS == 20)
    check("samples/frame=960", RTP_SAMPLES_PER_FRAME == 960)
    check("bytes/frame=1920 (mono s16)", RTP_BYTES_PER_FRAME == 1920)
    check("derived samples==SRATE*ms/1000",
          RTP_SAMPLES_PER_FRAME == RTP_SRATE * RTP_FRAME_MS // 1000)
    check("derived bytes==samples*2",
          RTP_BYTES_PER_FRAME == RTP_SAMPLES_PER_FRAME * 2)
    pkt = 12 + RTP_BYTES_PER_FRAME
    check("datagram 1932B > 1500 MTU (board needs IP4_REASSEMBLY)",
          pkt == 1932 and pkt > 1500, "got %d" % pkt)


def test_ui_id_contract():
    print("UI element-ID contract (index.html <-> app.js):")
    html = open(os.path.join(HERE, "templates", "index.html"),
                encoding="utf-8").read()
    js = open(os.path.join(HERE, "static", "app.js"), encoding="utf-8").read()
    ids = set(re.findall(r'id="(\w+)"', html))
    used = set(re.findall(r'\$\("(\w+)"\)', js))
    # eqColumn() builds the EQ slider columns at runtime (preamp + one per
    # band), so their ids exist only in the DOM, never in index.html source.
    dynamic = {"eqPre", "eqPreDb"}
    dynamic |= {"eqb%d" % i for i in range(10)} | {"eqd%d" % i for i in range(10)}
    missing = sorted(used - ids - dynamic)
    check("every $(\"id\") in app.js exists in index.html",
          not missing, "missing=%s" % missing if missing else "%d ids" % len(ids))
    check("index.html loads app.js", "/static/app.js" in html)
    check("index.html loads style.css", "/static/style.css" in html)


def test_pacing():
    """The sender must not free-run: ~50 frames/s (1920 B / 20 ms), not ffmpeg's
    decode rate. Regression test for the `0 < ahead < 0.1` pacing bug that made
    the board drop packets."""
    print("Real-time pacing (measured over the wire, no ffmpeg needed):")
    import socket as _s
    from audio_player.player import Player

    rx = _s.socket(_s.AF_INET, _s.SOCK_DGRAM)
    rx.bind(("127.0.0.1", 0))
    rx.setblocking(False)
    port = rx.getsockname()[1]

    saved = cfg.nodes
    cfg.nodes = [{"ip": "127.0.0.1", "port": port, "name": "selftest"}]
    try:
        p = Player()
        p._sock = _s.socket(_s.AF_INET, _s.SOCK_DGRAM)
        p._sock.setblocking(False)
        p._running = True
        p._base_samples = 0
        p._start_wall = 0.0
        p._bytes_sent = 0
        frame = b"\x00" * RTP_BYTES_PER_FRAME
        got = 0
        t0 = time.monotonic()
        while time.monotonic() - t0 < 1.0:
            p._send_frame(frame)
            while True:
                try:
                    rx.recv(2048)
                    got += 1
                except BlockingIOError:
                    break
        p._sock.close()
        # 1 s at 50 frames/s; allow slack for Windows timer granularity.
        check("sent ~50 frames in 1 s (real time)", 42 <= got <= 58,
              "got %d (would be ~150 if pacing were off)" % got)
        check("packet size is 12+1920", len(rtp_header(0, 0, 0)) + RTP_BYTES_PER_FRAME == 1932)
    finally:
        cfg.nodes = saved
        rx.close()


def test_position_across_restart():
    """seek()/set_volume() restart the pipeline; position must stay absolute."""
    print("Position survives pipeline restarts:")
    from audio_player.player import Player
    p = Player()
    p._running = True
    p._base_samples = 0
    p._bytes_sent = 2 * 9600                    # 9600 samples into the file
    check("fresh pipeline reports 9600", p.sample_position == 9600)
    # what seek() does: stop() zeroes the counter, then rebase
    p._base_samples = RTP_SRATE * 100           # seeked to 100 s
    p._bytes_sent = 2 * 4800                    # +0.1 s sent since
    check("after seek to 100s -> 100.1s",
          p.sample_position == RTP_SRATE * 100 + 4800,
          "got %d" % p.sample_position)
    p._running = False
    check("stopped reports 0", p.sample_position == 0)


def test_config():
    print("Config (one node for V1):")
    check("at least one node configured", len(cfg.nodes) >= 1)
    check("node has ip/port/name",
          all(k in cfg.nodes[0] for k in ("ip", "port", "name")))
    check("library_root is a directory", os.path.isdir(cfg.library_root),
          cfg.library_root)


def test_eq():
    """10-band EQ: chain insertion, clamping, validation, persistence."""
    print("Equalizer (VLC 10-band, limiter must stay last):")
    import tempfile
    from audio_player.player import Player
    from audio_player import config as cf
    p = Player()
    saved = (cfg.eq_enabled, cfg.eq_preamp_db, list(cfg.eq_gains),
             dict(cfg.eq_user_presets), cfg.eq_presets_path)
    with tempfile.TemporaryDirectory() as td:
        cfg.eq_presets_path = os.path.join(td, "eq.json")
        try:
            check("10 VLC bands, 60..16k", len(cf.EQ_BANDS) == 10 and
                  cf.EQ_BANDS[0] == 60 and cf.EQ_BANDS[-1] == 16000)
            # Built-in presets are gains-only lists; /api/eq/preset wraps them
            # in a dict before use. Mirror that contract here.
            bp = cf.EQ_BUILTIN_PRESETS["Mid Cut (speaker)"]
            if isinstance(bp, list):
                bp = {"preamp_db": 0.0, "gains": bp}
            check("built-in preset normalizes to dict",
                  isinstance(bp, dict) and len(bp["gains"]) == 10)
            check("all built-in presets valid",
                  all(len(g) == 10 and all(-12 <= x <= 12 for x in g)
                      for g in cf.EQ_BUILTIN_PRESETS.values()))
            cfg.eq_enabled = False
            check("EQ off -> no equalizer filter",
                  "equalizer" not in p._af_chain(1.0))
            cfg.eq_enabled = True
            cfg.eq_gains = [0, -4, 0, -6, 0, 0, 0, 0, 0, 0]
            af = p._af_chain(1.0)
            check("EQ on -> band filters for 170/600 Hz",
                  "equalizer=f=170" in af and "equalizer=f=600" in af)
            check("limiter stays LAST in chain",
                  af.rfind("alimiter") > af.rfind("equalizer"))
            cfg.eq_gains = [0.0] * 10
            check("flat EQ adds no band filters",
                  "equalizer" not in p._af_chain(1.0))
            p.set_eq(enabled=True, preamp_db=-99, gains=[99] * 10)
            check("preamp clamped to +-12 dB", cfg.eq_preamp_db == cf.EQ_MIN_DB)
            check("gains clamped to +-12 dB", cfg.eq_gains[0] == cf.EQ_MAX_DB)
            bad_len = False
            try:
                p.set_eq(gains=[0, 0, 0])
            except ValueError:
                bad_len = True
            check("wrong gains length rejected", bad_len)
            cfg.eq_gains = [1.5, 0, 0, 0, 0, 0, 0, 0, 0, -2.5]
            cfg.eq_preamp_db = -1.0
            cfg.eq_user_presets["__t"] = {"preamp_db": 2.0,
                                          "gains": [3, 0, 0, 0, 0, 0, 0, 0, 0, 0]}
            cf.eq_save()
            cfg.eq_enabled = False
            cfg.eq_preamp_db = 0.0
            cfg.eq_gains = [0.0] * 10
            cfg.eq_user_presets = {}
            cf.eq_load()
            check("state survives save/load (fresh-start path)",
                  cfg.eq_preamp_db == -1.0 and cfg.eq_gains[0] == 1.5 and
                  cfg.eq_gains[-1] == -2.5 and
                  cfg.eq_user_presets["__t"]["gains"][0] == 3)
        finally:
            (cfg.eq_enabled, cfg.eq_preamp_db, cfg.eq_gains,
             cfg.eq_user_presets, cfg.eq_presets_path) = saved
            cf.eq_save()


def test_deps():
    """The dependency list must be identical in deps.py, requirements.txt
    and pyproject.toml. Three copies of one list is three chances to rot;
    this is the check that stops it."""
    print("Dependencies (deps.py == requirements.txt == pyproject.toml):")
    from audio_player import deps
    import tomllib

    def names(specs):
        out = set()
        for s in specs:
            n = re.split(r"[<>=!~\[; ]", s.strip(), 1)[0].strip().lower()
            if n:
                out.add(n)
        return out

    # 1. required packages really are importable here
    check("all REQUIRED packages import", not deps.missing(),
          "missing=%s" % [d for d, _ in deps.missing()])
    check("ensure() passes on this machine", deps.ensure())
    check("install_command() points at requirements.txt",
          "requirements.txt" in deps.install_command())

    # 2. requirements.txt declares exactly deps' list
    req_lines = [ln for ln in deps.REQUIREMENTS.read_text(encoding="utf-8")
                 .splitlines()
                 if ln.strip() and not ln.strip().startswith("#")]
    req = names(req_lines)
    want = names([d for d, _ in deps.REQUIRED + deps.RECOMMENDED])
    check("requirements.txt matches deps.py", req == want,
          "req-only=%s deps-only=%s" % (sorted(req - want), sorted(want - req)))

    # 3. pyproject.toml declares the same set
    proj = tomllib.loads((deps.ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    check("pyproject dependencies match requirements.txt",
          names(proj["project"]["dependencies"]) == req,
          "proj=%s" % sorted(names(proj["project"]["dependencies"])))

    # 4. nothing the app never imports is declared as a hard dependency.
    #    Look for real import statements, not the bare word: a comment that
    #    says "no eventlet" must not trip this.
    src = "\n".join((deps.ROOT / "audio_player" / f).read_text(encoding="utf-8")
                    for f in ("app.py", "config.py", "library.py", "player.py"))
    hard = names([d for d, _ in deps.REQUIRED])
    for mod in ("eventlet", "requests", "numpy"):
        imported = re.search(r"^\s*(?:import\s+%s\b|from\s+%s\b)"
                             % (mod, mod), src, re.M)
        check("'%s' is neither imported nor required" % mod,
              not imported and mod not in hard)


def test_modules_import():
    """Every module must at least import.

    This is the cheapest possible guard, and it matters: the other checks only
    import config/player, so a syntax error in a module they never touch (a
    mis-indented docstring in app.py, say) used to pass the whole run.
    """
    print("Every module imports cleanly:")
    import importlib
    for name in ("config", "library", "player", "deps", "app"):
        try:
            importlib.import_module("audio_player." + name)
            ok, why = True, ""
        except Exception as e:
            ok, why = False, "%s: %s" % (type(e).__name__, e)
        check("audio_player.%s imports" % name, ok, why)


def test_ui_styles():
    """The stylesheet must actually cover the UI.

    Two silent failures this prevents: a class the markup uses with no rule at
    all (renders unstyled and nobody notices until someone looks), and CSS that
    stops parsing because a brace is unbalanced.
    """
    print("Stylesheet covers the markup:")
    css_path = os.path.join(HERE, "static", "style.css")
    html_path = os.path.join(HERE, "templates", "index.html")
    css = open(css_path, encoding="utf-8").read()
    html = open(html_path, encoding="utf-8").read()
    js = open(os.path.join(HERE, "static", "app.js"), encoding="utf-8").read()

    check("CSS braces balanced", css.count("{") == css.count("}"),
          "%d { vs %d }" % (css.count("{"), css.count("}")))

    # Classes the markup uses...
    used = set()
    for m in re.findall(r'class="([^"]+)"', html):
        used.update(m.split())
    # ...plus the ones app.js assigns to the DOM it builds at runtime.
    for m in re.findall(r'className\s*=\s*"([^"]+)"', js):
        used.update(m.split())
    for m in re.findall(r"classList\.(?:add|toggle|remove)\(\s*'([^']+)'", js):
        used.add(m)
    for m in re.findall(r'className\s*=\s*"([^"]*?)"\s*\+', js):
        for part in re.findall(r'"([^"]*)"', m):
            used.update(p for p in part.split() if p)
    # State hooks: set or cleared by app.js at runtime rather than declared in
    # a rule (the selector exists as a compound, e.g. ".app.nav-open .sidebar").
    state = {"active", "playing", "sel", "open", "preamp", "nav-open"}
    styled = set(re.findall(r"\.([A-Za-z_][\w-]*)", css))
    missing = sorted(c for c in used - styled if c not in state)
    check("every class in the markup/js has a CSS rule", not missing,
          "unstyled=%s" % missing if missing else "%d classes" % len(used))

    check("stylesheet defines dark and light themes",
          "prefers-color-scheme: light" in css and "--accent:" in css)
    check("stylesheet honours prefers-reduced-motion",
          "prefers-reduced-motion" in css)
    # An external asset is a LOAD reference (src/href/url()/@import), not prose
    # that happens to contain a URL - the Help text legitimately names the
    # board's own address.
    external = re.findall(r'(?:src|href)\s*=\s*["\']https?://', html, re.I)
    external += re.findall(r'url\(\s*["\']?https?://', css, re.I)
    external += re.findall(r'@import', css, re.I)
    check("no external assets (the UI must work offline)", not external,
          "found %d" % len(external) if external else "all assets local")


def main():
    print("audio_player selftest\n")
    test_modules_import()
    test_rtp_header()
    test_frame_math()
    test_pacing()
    test_position_across_restart()
    test_eq()
    test_deps()
    test_ui_id_contract()
    test_ui_styles()
    test_config()
    print("")
    if FAILS:
        print("FAILED %d check(s): %s" % (len(FAILS), ", ".join(FAILS)))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
