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
  python send_pcm.py loop 1234 1.0          # VLC mode: stream PC speaker output (VLC controls everything)
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
    # decode: 48kHz, mono, 16-bit LE raw PCM on stdout.
    # chain (anti-bass-masking + reduced overall volume for 2-inch speaker):
    #   highpass 180Hz → bass shelf -16dB@220 → heavy compressor → limiter
    #   → volume 0.30 (board x2 gain → 0.6 peak, comfortably below clipping).
    proc = subprocess.Popen(
        [ffmpeg, "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR),
         "-f", "s16le",
         "-af", f"highpass=f=180,bass=g=-16:f=220,acompressor=threshold=0.2:ratio=5:attack=15:release=200,alimiter=limit=0.75,volume={0.30 * vol}",
         "pipe:1"],
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

def loop_mode(port, vol):
    """VLC mode: capture the PC's speaker output (WASAPI loopback — whatever
    VLC is playing) and stream it to the board in real time. VLC controls
    play/pause/volume; the board mirrors the PC speakers."""
    import numpy as np
    import pyaudiowpatch as pyaudio
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", port))
    s.listen(1)
    print(f"listening on 0.0.0.0:{port} — waiting for board... (VLC loopback mode)")
    conn, addr = s.accept()
    print(f"ACCEPTED connection from {addr[0]}:{addr[1]} — streaming PC audio loopback", flush=True)
    pa = pyaudio.PyAudio()
    dev = pa.get_default_wasapi_loopback()
    ch = int(dev["maxInputChannels"])
    rate = int(dev["defaultSampleRate"])
    print(f"loopback device: {dev['name']} ({ch}ch @ {rate}Hz)", flush=True)
    frames = 1024
    sent = 0
    try:
        stream = pa.open(format=pyaudio.paInt16, channels=ch, rate=rate,
                         input=True, input_device_index=dev["index"],
                         frames_per_buffer=frames)
        while True:
            raw = stream.read(frames, exception_on_overflow=False)
            x = np.frombuffer(raw, dtype="<i2").astype(np.float64)
            x = x.reshape(-1, ch).mean(axis=1)              # stereo → mono mixdown
            if rate != SR:                                   # resample to 48k
                n_out = int(round(len(x) * SR / rate))
                x = np.interp(np.linspace(0, len(x) - 1, n_out), np.arange(len(x)), x)
            pcm = (np.clip(x * vol, -32767, 32767)).astype("<i2").tobytes()
            conn.sendall(pcm)
            sent += len(pcm)
            if sent % (frames * 2 * 50) == 0:
                print(f"sent {sent} bytes ({sent/(2*SR):.1f}s)", flush=True)
    except (BrokenPipeError, ConnectionResetError) as e:
        print(f"\nconnection lost: {e}")
    except Exception as e:
        print(f"\nloopback error: {e}")
    finally:
        try: stream.stop_stream(); stream.close()
        except Exception: pass
        pa.terminate()
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
    elif len(sys.argv) >= 2 and sys.argv[1] == "loop":
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 1234
        vol = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
        loop_mode(port, vol)
    else:
        print(__doc__)
