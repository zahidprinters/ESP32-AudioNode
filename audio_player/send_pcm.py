#!/usr/bin/env python3
"""RTP L16/UDP sender. Modes: tone, file, loop.
Examples:
  python send_pcm.py tone <board-ip> 1234 30 1000 0.5
  python send_pcm.py file song.mp3 <board-ip> 1234 0.7
  python send_pcm.py loop <board-ip> 1234 0.8
RTP hdr (12 bytes, net order): V=2(0x80)|PT=96(0x60), seq(+1), ts(+960=samples), SSRC=0xDEADBEEF"""
import socket, struct, sys, math, time

SR = 48000; FRAME_SAMPLES = 960; FRAME_BYTES = FRAME_SAMPLES * 2; RTP_PT = 96; SSRC = 0xDEADBEEF

def make_rtp_header(seq, ts):
    """Build a 12-byte RTP header (V=2, PT=96) for this fixed-SSRC sender."""
    return struct.pack("!BBHII", 0x80, RTP_PT, seq & 0xFFFF, ts, SSRC)

def make_tone_frame(freq, vol, start_sample):
    """One 20 ms frame of a sine wave, as 16-bit LE mono PCM bytes.
        `start_sample` keeps the wave phase continuous across frames."""
    out = bytearray(); amp = int(32000 * vol)
    for i in range(FRAME_SAMPLES):
        v = int(amp * math.sin(2 * math.pi * freq * (start_sample + i) / SR))
        out += struct.pack("<h", v)
    return out

def tone_mode(ip, port, seconds, freq, vol):
    """Stream a generated tone for `seconds`, paced in real time. Returns nothing."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"sending RTP tone {freq}Hz to {ip}:{port} for {seconds}s (vol={vol})", flush=True)
    seq = 0; ts = 0; start_sample = 0; t0 = time.time()
    try:
        while (time.time() - t0) < seconds:
            sock.sendto(make_rtp_header(seq, ts) + make_tone_frame(freq, vol, start_sample), (ip, port))
            seq += 1; ts += FRAME_SAMPLES; start_sample += FRAME_SAMPLES
            target = ts / SR; lag = target - (time.time() - t0)
            if lag > 0: time.sleep(lag)
            if seq % 50 == 0: print(f"  sent {seq} frames ({seq * FRAME_SAMPLES / SR:.1f}s)", flush=True)
        print(f"done: {seq} frames ({seq * FRAME_SAMPLES / SR:.1f}s) in {time.time()-t0:.1f}s")
    except KeyboardInterrupt: print(f"\ninterrupted after {seq}")
    finally: sock.close()

def file_mode(path, ip, port, vol):
    """Decode a file with ffmpeg and stream it, paced in real time.
        Returns nothing."""
    import subprocess, imageio_ffmpeg
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"sending RTP file '{path}' to {ip}:{port} (vol={vol})", flush=True)
    cmd = [ffmpeg, "-i", path,
           "-af", f"highpass=f=150,equalizer=f=200:width_type=h:width=100:g=-12,"
                  f"acompressor=threshold=-20dB:ratio=4:attack=5:release=100,"
                  f"alimiter=limit=0.75,volume={vol}",
           "-ar", str(SR), "-ac", "1", "-f", "s16le", "-loglevel", "error", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    seq = 0; ts = 0; t0 = None
    try:
        while True:
            pcm = proc.stdout.read(FRAME_BYTES)
            if not pcm or len(pcm) < FRAME_BYTES: break
            sock.sendto(make_rtp_header(seq, ts) + pcm, (ip, port))
            seq += 1; ts += FRAME_SAMPLES
            if t0 is None: t0 = time.time()
            else:
                target = ts / SR; lag = target - (time.time() - t0)
                if lag > 0: time.sleep(lag)
            if seq % 50 == 0: print(f"  sent {seq} frames ({seq * FRAME_SAMPLES / SR:.1f}s)", flush=True)
        elapsed = time.time() - t0 if t0 else 0
        print(f"done: {seq} frames ({seq * FRAME_SAMPLES / SR:.1f}s) in {elapsed:.1f}s")
    except KeyboardInterrupt: print(f"\ninterrupted after {seq}")
    finally: proc.kill(); sock.close()

def loop_mode(ip, port, vol):
    """Capture the PC's default WASAPI loopback device and stream it (Windows
        only; needs numpy and PyAudioWPatch). Returns nothing."""
    import numpy as np, pyaudiowpatch as pyaudio
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"sending RTP loopback to {ip}:{port} (vol={vol})", flush=True)
    pa = pyaudio.PyAudio()
    dev = pa.get_default_wasapi_loopback()
    ch = int(dev["maxInputChannels"]); rate = int(dev["defaultSampleRate"])
    print(f"loopback: {dev['name']} ({ch}ch @ {rate}Hz)", flush=True)
    frames = FRAME_SAMPLES if rate == SR else int(round(FRAME_SAMPLES * rate / SR))
    seq = 0; ts = 0
    stream = pa.open(format=pyaudio.paInt16, channels=ch, rate=rate,
                     input=True, input_device_index=dev["index"], frames_per_buffer=frames)
    try:
        while True:
            raw = stream.read(frames, exception_on_overflow=False)
            x = np.frombuffer(raw, dtype="<i2").astype(np.float64).reshape(-1, ch).mean(axis=1)
            if rate != SR:
                n_out = int(round(len(x) * SR / rate))
                x = np.interp(np.linspace(0, len(x) - 1, n_out), np.arange(len(x)), x)
            if len(x) > FRAME_SAMPLES: x = x[:FRAME_SAMPLES]
            elif len(x) < FRAME_SAMPLES: x = np.pad(x, (0, FRAME_SAMPLES - len(x)))
            pcm = (np.clip(x * vol, -32767, 32767)).astype("<i2").tobytes()
            sock.sendto(make_rtp_header(seq, ts) + pcm, (ip, port))
            seq += 1; ts += FRAME_SAMPLES
            if seq % 50 == 0: print(f"  sent {seq} frames ({seq * FRAME_SAMPLES / SR:.1f}s)", flush=True)
    except KeyboardInterrupt: print(f"\ninterrupted after {seq}")
    finally:
        try: stream.stop_stream(); stream.close()
        except Exception: pass
        pa.terminate(); sock.close()

if __name__ == "__main__":
    if len(sys.argv) < 2: print(__doc__)
    elif sys.argv[1] == "tone":
        tone_mode(sys.argv[2] if len(sys.argv) > 2 else "<board-ip>",
                  int(sys.argv[3]) if len(sys.argv) > 3 else 1234,
                  int(sys.argv[4]) if len(sys.argv) > 4 else 30,
                  int(sys.argv[5]) if len(sys.argv) > 5 else 1000,
                  float(sys.argv[6]) if len(sys.argv) > 6 else 0.5)
    elif sys.argv[1] == "file":
        if len(sys.argv) < 4: print("usage: send_pcm.py file <path> <ip> [port] [vol]"); sys.exit(1)
        file_mode(sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 1234,
                  float(sys.argv[5]) if len(sys.argv) > 5 else 0.7)
    elif sys.argv[1] == "loop":
        loop_mode(sys.argv[2] if len(sys.argv) > 2 else "<board-ip>",
                  int(sys.argv[3]) if len(sys.argv) > 3 else 1234,
                  float(sys.argv[4]) if len(sys.argv) > 4 else 0.8)
    else: print(__doc__)
