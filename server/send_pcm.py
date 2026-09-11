#!/usr/bin/env python3
"""send_pcm.py — canonical TCP test sender (single file, no duplicates).

Modes:
  server:  python send_pcm.py server [port]      — accept one board connection, log traffic (M2 test)
  stream:  python send_pcm.py stream <ip> [port] [seconds] [freq] [vol]
           — connect to... no: board is client, so 'stream' LISTENS and sends tone PCM
             python send_pcm.py stream [port] [seconds] [freq] [vol]

Examples:
  python send_pcm.py server                 # M2: just accept + log
  python send_pcm.py stream 60 1000 0.5     # M3: send 60s of 1kHz tone at 0.5 vol to first board that connects
  python send_pcm.py file song.mp3 1234 1.0 # stream a real audio file (mp3 etc.) decoded to 48k/16b/mono PCM
"""
import socket
import struct
import sys
import math
import time

SR = 48000  # 16-bit mono

def make_tone_chunk(freq, vol, start_sample, n):
    out = bytearray()
    amp = int(32000 * vol)
    for i in range(n):
        v = int(amp * math.sin(2 * math.pi * freq * (start_sample + i) / SR))
        out += struct.pack("<h", v)
    return out

def server_mode(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", port))
    s.listen(1)
    print(f"listening on 0.0.0.0:{port} ...")
    conn, addr = s.accept()
    print(f"ACCEPTED connection from {addr[0]}:{addr[1]}")
    try:
        total = 0
        conn.settimeout(60)
        while True:
            data = conn.recv(4096)
            if not data:
                print("client disconnected")
                break
            total += len(data)
            print(f"recv {len(data)} bytes (total {total})")
    except socket.timeout:
        print("idle timeout (60s) — closing")
    finally:
        conn.close()
        s.close()

def stream_mode(port, seconds, freq, vol):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", port))
    s.listen(1)
    print(f"listening on 0.0.0.0:{port} — waiting for board...")
    conn, addr = s.accept()
    print(f"ACCEPTED connection from {addr[0]}:{addr[1]} at t={time.time():.2f} — streaming {freq}Hz for {seconds}s", flush=True)
    print(f"sent first chunk t={time.time():.2f}", flush=True)
    conn.sendall(make_tone_chunk(freq, vol, 0, 1024))
    start = 1024
    sent = 2048
    t0 = time.time()
    chunk_samples = 1024
    try:
        while (time.time() - t0) < seconds:
            chunk = make_tone_chunk(freq, vol, start, chunk_samples)
            conn.sendall(chunk)
            start += chunk_samples
            sent += len(chunk)
            # real-time pacing: 1024 samples = 21.33ms per chunk
            target = sent / (2 * SR)
            lag = target - (time.time() - t0)
            if lag > 0:
                time.sleep(lag)
            print(f"sent {sent} bytes ({sent/(2*SR):.1f}s of audio) t={time.time():.2f}")
        print(f"\ndone: sent {sent} bytes in {time.time()-t0:.1f}s")
    except (BrokenPipeError, ConnectionResetError) as e:
        print(f"\nconnection lost: {e}")
    finally:
        conn.close()
        s.close()

def file_mode(path, port, vol):
    """Listen for the board, then decode an audio file (mp3 etc.) via ffmpeg
    to 48kHz/16-bit/mono PCM and stream it in real time."""
    import subprocess
    import imageio_ffmpeg
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", port))
    s.listen(1)
    print(f"listening on 0.0.0.0:{port} — waiting for board... (file: {path})")
    conn, addr = s.accept()
    print(f"ACCEPTED connection from {addr[0]}:{addr[1]} — streaming file", flush=True)
    # decode: 48kHz, mono, 16-bit LE raw PCM on stdout, -7dB peak headroom
    # (board applies x2 = +6dB digital gain; headroom prevents clipping).
    # NOTE: acompressor/alimiter chain = sender slower than real-time →
    # periodic underruns (long tone every few sec) — REVERTED, keep simple.
    proc = subprocess.Popen(
        [ffmpeg, "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR),
         "-f", "s16le", "-af", f"highpass=f=120,volume={0.45 * vol}", "pipe:1"],
        stdout=subprocess.PIPE)
    sent = 0
    t0 = None
    chunk = 4096  # 1024 samples = 21.33ms per chunk
    try:
        while True:
            pcm = proc.stdout.read(chunk)
            if not pcm:
                break
            # real-time pacing: bytes/2 = samples; samples/SR = seconds
            sent += len(pcm)
            target = sent / (2 * SR)
            if t0 is None:
                t0 = time.time()
            else:
                lag = target - (time.time() - t0)
                if lag > 0:
                    time.sleep(lag)
            conn.sendall(pcm)
            if sent % (chunk * 50) == 0:
                print(f"sent {sent} bytes ({sent/(2*SR):.1f}s of audio)", flush=True)
        print(f"\ndone: sent {sent} bytes ({sent/(2*SR):.1f}s) in {time.time()-t0:.1f}s")
    except (BrokenPipeError, ConnectionResetError) as e:
        print(f"\nconnection lost: {e}")
    finally:
        proc.kill()
        conn.close()
        s.close()

if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "server":
        server_mode(int(sys.argv[2]) if len(sys.argv) > 2 else 1234)
    elif len(sys.argv) >= 2 and sys.argv[1] == "stream":
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 1234
        secs = int(sys.argv[3]) if len(sys.argv) > 3 else 30
        freq = int(sys.argv[4]) if len(sys.argv) > 4 else 1000
        vol = float(sys.argv[5]) if len(sys.argv) > 5 else 0.5
        stream_mode(port, secs, freq, vol)
    elif len(sys.argv) >= 3 and sys.argv[1] == "file":
        path = sys.argv[2]
        port = int(sys.argv[3]) if len(sys.argv) > 3 else 1234
        vol = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0
        file_mode(path, port, vol)
    else:
        print(__doc__)
