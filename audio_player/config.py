# audio_player config — single place for defaults
# Board IPs, library root, HTTP/WS host:port, RTP constants delegate to player.py.

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# RTP constants (MUST match firmware ARCHITECTURE.md protocol spec)
# ---------------------------------------------------------------------------
RTP_SRATE              = 48000          # Hz
RTP_BIT_DEPTH          = 16
RTP_CHANNELS           = 1              # mono
RTP_FRAME_MS           = 20
RTP_SAMPLES_PER_FRAME  = 960            # = SRATE * FRAME_MS / 1000
RTP_BYTES_PER_FRAME    = 1920           # = SAMPLES_PER_FRAME * BIT_DEPTH / 8
RTP_PT                 = 96             # dynamic L16/48k/mono
RTP_PORT               = 1234           # board listener port

# ffmpeg (static binary shipped by imageio-ffmpeg — no system install needed)
try:
    from imageio_ffmpeg import get_ffmpeg_exe
    FFMPEG_EXE = get_ffmpeg_exe()
except Exception as e:
    import logging
    logging.getLogger("audio_player").error(
        "imageio_ffmpeg.get_ffmpeg_exe failed: %s", e)
    FFMPEG_EXE = "ffmpeg"                 # fallback to system PATH

# ---------------------------------------------------------------------------
# Config — one mutable object for the whole app
# ---------------------------------------------------------------------------
class Config:
    """Per-session config. V1 = one node; V2+ appends more.

    ``library_root`` is a directory the UI picker sets at runtime (V1 default
    points at the repo's shipped ``media/`` folder).
    """
    def __init__(self):
        # One node now (V1). Each entry: ip, port, name.
        self.nodes = [
            {"ip": "<board-ip>", "port": RTP_PORT, "name": "node-1"},
        ]
        # Default library root = the repo's media/ folder. Created on import so a
        # fresh clone works immediately without shipping any audio in git.
        self.library_root = str(Path(__file__).resolve().parent / "media")
        os.makedirs(self.library_root, exist_ok=True)
        self.default_volume = 1.0
        # HTTP + WS
        self.host = "0.0.0.0"
        self.port = 5000
        # Player: headroom for the pump's internal buffer (a few frames).
        self.pcm_buffer_bytes = RTP_BYTES_PER_FRAME * 8

cfg = Config()
