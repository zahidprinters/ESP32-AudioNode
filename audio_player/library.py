# audio_player.library — MP3 folder scan + duration.
#
# Known ceiling: duration is obtained by decoding the whole file with ffmpeg
# (no ffprobe shipped by imageio-ffmpeg). Slow for big libraries; V2 caches
# durations on disk. V1 (one file) is fine.

import os
import re
import subprocess
import logging
from audio_player.config import FFMPEG_EXE

_log = logging.getLogger("audio_player.library")
AUDIO_EXTS = {".mp3", ".flac", ".wav", ".m4a", ".aac", ".ogg", ".wma"}


def scan_library(root: str) -> list:
    """Return [{path, name, duration_s, size_bytes}, ...] for audio files under
    ``root`` (recursive). Duration from ffmpeg decode-to-null Duration header."""
    root = str(root)
    out = []
    if not os.path.isdir(root):
        return out
    for dirpath, _dirs, files in os.walk(root):
        for fn in sorted(files):
            low = fn.lower()
            if not any(low.endswith(ext) for ext in AUDIO_EXTS):
                continue
            full = os.path.join(dirpath, fn)
            try:
                dur = _duration(FFMPEG_EXE, full)
            except Exception as e:
                _log.warning("library: duration failed for %s: %s", full, e)
                dur = None
            try:
                sz = os.path.getsize(full)
            except Exception:
                sz = 0
            out.append({"path": full, "name": fn,
                        "duration_s": dur, "size_bytes": sz})
    return out


def _duration(ffmpeg_exe: str, path: str):
    """Parse "Duration: HH:MM:SS.mmm" from ffmpeg -i <file> -f null - stderr."""
    try:
        p = subprocess.run(
            [ffmpeg_exe, "-i", path, "-f", "null", "-"],
            capture_output=True, text=True, timeout=120,
        )
    except subprocess.TimeoutExpired:
        return None
    blob = (p.stderr or "") + (p.stdout or "")
    m = re.search(r"Duration:\s+(\d+):(\d+):(\d+)\.(\d+)", blob)
    if not m:
        return None
    h, mi, s, frac = [int(x) for x in m.groups()]
    return h * 3600 + mi * 60 + s + frac / 1000.0
