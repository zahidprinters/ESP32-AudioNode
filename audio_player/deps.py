# audio_player.deps — the one place that knows what the server needs.
#
# Single source of truth for the dependency list, used by the app, the
# self-check and the Windows launcher, so those three cannot drift apart.
# Only imports the standard library, so it can report missing packages
# *instead of* dying on an ImportError three frames deep.
#
# Known ceilings:
#   * presence is verified by import, not by version, so a too-old
#     Flask passes here and fails later. requirements.txt holds the
#     minimums; a lockfile would be the upgrade path.
#   * the log is appended to, never rotated — one short line per start,
#     so it stays small in practice.

import importlib
import importlib.metadata as metadata
import os
import subprocess
import sys
import time
from pathlib import Path

# (distribution name on PyPI, module to import)
REQUIRED = (
    ("flask", "flask"),
    ("flask-socketio", "flask_socketio"),
    ("imageio-ffmpeg", "imageio_ffmpeg"),
)

# Optional: without it the Socket.IO client falls back to long polling.
# Everything still works, just with more requests.
RECOMMENDED = (
    ("simple-websocket", "simple_websocket"),
)

ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS = ROOT / "requirements.txt"
LOG = ROOT / "logs" / "app.log"


def log_path():
    return LOG


def append_log(msg):
    """Best-effort; never raise, never print. Returns True if written."""
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write("%s  %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
        return True
    except OSError:
        return False


def _imports(mod):
    try:
        importlib.import_module(mod)
        return True
    except Exception:
        return False


def missing():
    """Required distributions that will not import -> [(dist, module), ...]."""
    return [(d, m) for d, m in REQUIRED if not _imports(m)]


def absent_optional():
    """Recommended-but-not-required distributions that are not installed."""
    return [(d, m) for d, m in RECOMMENDED if not _imports(m)]


def versions():
    """{dist: version or None} for everything we know about."""
    out = {}
    for dist, _ in REQUIRED + RECOMMENDED:
        try:
            out[dist] = metadata.version(dist)
        except Exception:
            out[dist] = None
    return out


def install_command():
    """The exact command that fixes this interpreter, quoted for copy/paste."""
    return '"%s" -m pip install -r "%s"' % (sys.executable, REQUIREMENTS)


def install():
    """pip install the requirements into *this* interpreter.

    Explicitly never runs by itself: the launcher and the app only call it
    when the user asks. Silently installing into whatever `python` resolves
    to can modify a system install or the ESP-IDF venv.
    """
    cmd = [sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS)]
    print("Installing dependencies for this Python:")
    print("   " + " ".join(cmd), flush=True)
    try:
        rc = subprocess.call(cmd)
    except OSError as e:
        print("   install could not start: %s" % e, flush=True)
        append_log("dependency install could not start: %s" % e)
        return False
    if rc != 0:
        append_log("dependency install failed, pip exit %d" % rc)
        return False
    return not missing()


def _block(gap, optional_gap):
    names = ", ".join(d for d, _ in gap)
    lines = [
        "",
        "  ERROR: the server cannot start - required package(s) missing:",
        "         " + names,
        "",
        "  Fix it with this command, then run again:",
        "",
        "      " + install_command(),
        "",
    ]
    if optional_gap:
        lines += [
            "  Optional, not installed: %s"
            % ", ".join(d for d, _ in optional_gap),
            "  The UI still works without it (Socket.IO falls back to long",
            "  polling). Install it for WebSocket:",
            "",
            '      "%s" -m pip install %s' % (sys.executable, optional_gap[0][0]),
            "",
        ]
    return lines


def ensure():
    """Verify dependencies. True if the server can run.

    Prints a guide and records the outcome in the log when anything is
    missing, so a fresh machine is told exactly what to do instead of
    failing with a bare ImportError.
    """
    gap = missing()
    optional_gap = absent_optional()
    if gap:
        append_log("startup BLOCKED: missing %s (python=%s)"
                   % (", ".join(d for d, _ in gap), sys.executable))
        for line in _block(gap, optional_gap):
            print(line)
        return False
    vs = versions()
    append_log("startup OK: python=%s pkgs=%s"
               % (sys.executable,
                  ",".join("%s-%s" % (d, vs[d]) for d, _ in REQUIRED)))
    if optional_gap:
        append_log("startup OK (no optional: %s)"
                   % ", ".join(d for d, _ in optional_gap))
    return True
