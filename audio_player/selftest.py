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
    missing = sorted(used - ids)
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


def main():
    print("audio_player selftest\n")
    test_rtp_header()
    test_frame_math()
    test_pacing()
    test_position_across_restart()
    test_ui_id_contract()
    test_config()
    print("")
    if FAILS:
        print("FAILED %d check(s): %s" % (len(FAILS), ", ".join(FAILS)))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
