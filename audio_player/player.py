# audio_player.player — one ffmpeg -> RTP-L16/UDP sender pipeline per stream.
#
# Wire format (must match firmware exactly):
#   PCM 16-bit LE, 48000 Hz, mono; 20 ms frame = 960 samples = 1920 bytes
#   RTP: Version=2, PT=96, seq+1/frame, timestamp+960/frame (samples), SSRC=random
#   UDP destination = board IP :1234; source IP = sending host (whitelist in firmware)
#
# Known ceiling: MP3 seek is ffmpeg-dependent, not sample-accurate (good enough
# for a seek bar). Volume change requires a pipeline restart (ffmpeg volume is
# an input filter).

import os
import time
import socket
import struct
import subprocess
import threading
import logging
from audio_player.config import (RTP_SRATE, RTP_PT, RTP_SAMPLES_PER_FRAME,
                                  RTP_BYTES_PER_FRAME, FFMPEG_EXE, cfg, EQ_BANDS,
                                  EQ_MIN_DB, EQ_MAX_DB, eq_save)

_log = logging.getLogger("audio_player.player")


def rtp_header(seq: int, ts: int, ssrc: int) -> bytes:
    """12-byte RTP header: V=2, P=0, X=0, CC=0, M=0, PT=96."""
    b0 = 0x80 | (0 << 3) | 0          # V=2, P=0, X=0, CC=0
    b1 = (0 << 7) | RTP_PT            # M=0, PT=96
    return struct.pack("!BBHII", b0, b1,
                        seq & 0xFFFF, ts & 0xFFFFFFFF, ssrc & 0xFFFFFFFF)


class Player:
    """One ffmpeg decode -> RTP-send pipeline.

    Lifecycle: play() -> stop() -> play(...) . set_volume() and seek() restart
    the pipeline under the hood.
    """

    def __init__(self, status_cb=None):
        self._status_cb = status_cb or (lambda **kw: None)
        self._proc = None
        self._sock = None
        self._src = None
        self._volume = cfg.default_volume
        self._ssrc = 0
        self._seq = 0
        self._ts = 0
        self._running = False
        self._bytes_sent = 0
        self._base_samples = 0          # samples played before this pipeline
        self._start_wall = 0.0
        self._thread = None
        self._stop_ev = threading.Event()
        self._kill_ev = threading.Event()
        self._lock = threading.Lock()
        self._paused = False
        self._paused_samples = 0

    @property
    def running(self):
        return self._running

    @property
    def volume(self):
        return self._volume

    @property
    def bytes_sent(self):
        return self._bytes_sent

    @property
    def sample_position(self):
        """Playback position in samples (server-side: what we have sent)."""
        if self._paused:
            return self._paused_samples
        if not self._running:
            return 0
        # 2 bytes/sample, plus whatever was already played before this pipeline
        # started (seek and volume changes restart the pipeline, and position
        # is absolute from the start of the file).
        return self._base_samples + int(self._bytes_sent / 2)

    def play(self, source_path: str, volume: float = None):
        # If currently paused on the same source, resume instead of restarting.
        if self._paused and self._src and os.path.abspath(str(source_path)) == self._src:
            self.resume()
            return
        if self._running:
            self.stop()
        path = str(source_path)
        if not os.path.isfile(path):
            raise FileNotFoundError(path)
        vol = float(volume) if volume is not None else self._volume
        self._volume = vol
        self._src = path
        self._ssrc = int.from_bytes(os.urandom(4), "big") & 0xFFFFFFFF
        self._seq = 0
        self._ts = 0
        self._bytes_sent = 0
        self._base_samples = 0
        self._start_wall = 0.0          # anchored on the first sent frame
        self._running = True
        self._stop_ev.clear()
        self._kill_ev.clear()
        self._start_pipeline_at(path, vol, 0.0)
        self._status_cb(state="playing", src=os.path.basename(path),
                        src_path=os.path.abspath(path),
                        volume=self._volume)

    def stop(self):
        if not self._running and not self._paused:
            return
        self._kill_ev.set()
        self._stop_ev.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        self._kill_pipeline()
        self._running = False
        self._paused = False
        self._paused_samples = 0
        self._seq = 0
        self._ts = 0
        self._bytes_sent = 0
        self._base_samples = 0
        self._status_cb(state="stopped")

    def pause(self):
        """Pause streaming: kill the pipeline but keep position. Resume plays
        from the same spot — _base_samples is preserved."""
        if not self._running:
            return
        self._paused_samples = self.sample_position
        self._kill_ev.set()
        self._stop_ev.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        self._kill_pipeline()
        self._running = False
        self._paused = True
        self._status_cb(state="paused")

    def resume(self):
        """Resume from a paused state at the current position."""
        if not self._paused or not self._src:
            return
        pos_sec = self.sample_position / RTP_SRATE   # read while still paused
        self._running = True
        self._paused = False
        self._stop_ev.clear()
        self._kill_ev.clear()
        self._start_pipeline_at(self._src, self._volume, pos_sec)
        self._status_cb(state="playing", src=os.path.basename(self._src),
                        src_path=os.path.abspath(self._src),
                        volume=self._volume)

    def set_volume(self, volume: float):
        vol = max(0.0, min(10.0, float(volume)))
        if abs(vol - self._volume) < 1e-3:
            return
        self._volume = vol
        if self._running and self._src:
            # ffmpeg's volume is an input filter, so the pipeline must restart --
            # but at the *current* position, not from 0:00. seek() re-emits
            # playing + volume.
            self.seek(self.sample_position)
        else:
            self._status_cb(volume=vol)     # keep /api/status honest when idle

    def seek(self, sample_pos: int):
        """Restart at sample_pos samples from the start of the file."""
        if not self._running or not self._src:
            return
        pos_sec = max(0.0, sample_pos / RTP_SRATE)
        src = self._src
        vol = self._volume
        self.stop()                     # clears _running/_bytes_sent/_base_samples
        self._base_samples = int(max(0, sample_pos))
        self._ssrc = int.from_bytes(os.urandom(4), "big") & 0xFFFFFFFF
        self._seq = 0
        self._ts = 0
        self._bytes_sent = 0
        self._start_wall = 0.0          # anchored on the first sent frame
        self._running = True
        self._stop_ev.clear()
        self._kill_ev.clear()
        self._start_pipeline_at(src, vol, pos_sec)
        # The pipeline restart above resumes audio immediately; re-emit playing
        # so /api/status and the UI don't stay on "stopped" after a seek or a
        # live volume change (stop() inside this restart emits "stopped").
        self._status_cb(state="playing", src=os.path.basename(src),
                        src_path=os.path.abspath(src),
                        volume=self._volume)

    def _af_chain(self, vol: float) -> str:
        """ffmpeg chain tuned to the measured speaker (logs/2026-09-15_tone-diagnosis.md).

        highpass 65 Hz: song's 41 Hz sub-bass peak is unreproducible on this driver
        and only eats headroom / causes mid intermodulation. Gentle bass shelf:
        bass measured clean, -6@150 was over-corrected. Optional 10-band EQ
        (VLC band centers) sits before the compressor. Limiter is LAST with a
        0.5 ceiling so the board's x2 gain can never saturate, at ANY volume
        or EQ setting."""
        af = ""
        if cfg.sub_hp_hz > 0:
            af += f"highpass=f={cfg.sub_hp_hz:g},"
        if cfg.bass_cut_db < 0:
            af += f"lowshelf=f={cfg.bass_cut_hz:g}:g={cfg.bass_cut_db:g},"
        if cfg.eq_enabled:
            if abs(cfg.eq_preamp_db) >= 0.1:
                af += f"volume={10 ** (cfg.eq_preamp_db / 20.0):.4f},"
            for f_hz, g in zip(EQ_BANDS, cfg.eq_gains):
                if abs(g) >= 0.25:          # flat bands add nothing but filters
                    af += f"equalizer=f={f_hz:g}:t=q:w=1:g={g:+.1f},"
        af += (f"acompressor=threshold=-18dB:ratio=3:attack=10:release=150,"
               f"volume={vol:.3f},"
               f"alimiter=limit={cfg.dac_ceiling:g}:level=disabled")
        return af

    def _eq_snapshot(self):
        return {"enabled": cfg.eq_enabled, "preamp_db": cfg.eq_preamp_db,
                "gains": list(cfg.eq_gains)}

    def set_eq(self, enabled=None, preamp_db=None, gains=None):
        """Update EQ state, persist it, and apply live (pipeline restart at the
        current position — same mechanism as a volume change)."""
        if enabled is not None:
            cfg.eq_enabled = bool(enabled)
        if preamp_db is not None:
            cfg.eq_preamp_db = max(EQ_MIN_DB, min(EQ_MAX_DB, float(preamp_db)))
        if gains is not None:
            g = [float(x) for x in gains]
            if len(g) != len(EQ_BANDS):
                raise ValueError("expected %d band gains, got %d"
                                 % (len(EQ_BANDS), len(g)))
            cfg.eq_gains = [max(EQ_MIN_DB, min(EQ_MAX_DB, x)) for x in g]
        eq_save()
        if self._running and self._src:
            self.seek(self.sample_position)
        self._status_cb(eq=self._eq_snapshot())

    def _start_pipeline_at(self, src: str, vol: float, seek_sec: float):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setblocking(False)
        cmd = [
            FFMPEG_EXE,
            "-loglevel", "error",
            "-i", src,
            # ponytail: -ss AFTER -i = accurate seek (decodes from start);
            # input seek (-ss before -i) is fast but bitrate-estimated and
            # lands tens of seconds off on VBR MP3. Files are minutes long,
            # so the extra decode is <1 s. Upgrade path: maintain an index.
            "-ss", f"{seek_sec:.3f}",
            "-vn",
            "-ac", "1",
            "-ar", str(RTP_SRATE),
            "-sample_fmt", "s16",
            "-af", self._af_chain(vol),
            "-f", "s16le",
            "pipe:1",
        ]
        _log.info("player: ffmpeg %s", " ".join(cmd))
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=RTP_BYTES_PER_FRAME * 4,
            )
        except Exception as e:
            _log.error("player: failed to start ffmpeg: %s", e)
            self._running = False
            self._status_cb(state="error", error=str(e))
            self._proc = None
            return
        self._thread = threading.Thread(target=self._pump, name="rtp-pump",
                                        daemon=True)
        self._thread.start()

    def _kill_pipeline(self):
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.kill()
            except Exception:
                pass
            try:
                self._proc.wait(timeout=2.0)
            except Exception:
                pass
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
        self._proc = None

    def _pump(self):
        buf = bytearray()
        while not self._stop_ev.is_set():
            try:
                chunk = self._proc.stdout.read(RTP_BYTES_PER_FRAME * 4)
            except ValueError:
                break
            if not chunk:
                _log.info("player: ffmpeg EOF (stream ended naturally)")
                break
            buf.extend(chunk)
            while len(buf) >= RTP_BYTES_PER_FRAME:
                frame = bytes(buf[:RTP_BYTES_PER_FRAME])
                del buf[:RTP_BYTES_PER_FRAME]
                if self._kill_ev.is_set():
                    break
                self._send_frame(frame)
            if self._kill_ev.is_set():
                break
        _log.info("player: pump exiting, bytes_sent=%d", self._bytes_sent)
        # A naturally finished file must look exactly like a manual stop: without
        # clearing _running, sample_position keeps reporting the last byte count
        # and the UI stays "playing" forever after the stream ends.
        self._running = False
        self._kill_pipeline()
        self._status_cb(state="stopped")

    def _send_frame(self, frame: bytes):
        pkt = rtp_header(self._seq, self._ts, self._ssrc) + frame
        self._seq = (self._seq + 1) & 0xFFFF
        self._ts = (self._ts + RTP_SAMPLES_PER_FRAME) & 0xFFFFFFFF
        self._bytes_sent += len(frame)
        for n in cfg.nodes:
            try:
                self._sock.sendto(pkt, (n["ip"], int(n["port"])))
            except Exception as e:
                _log.warning("player: sendto %s:%s failed: %s",
                             n["ip"], n["port"], e)
        # Real-time pacing: never send faster than real time. The board's jitter
        # buffer overflows and drops packets if we do. Sleep off the whole lead,
        # capped per iteration so stop() stays responsive.
        # NB: an upper bound on `ahead` (e.g. `0 < ahead < 0.1`) looks harmless
        # but silently disables pacing the moment we run >100 ms ahead — which
        # happens immediately, since ffmpeg hands us 4 frames per read — and the
        # sender then free-runs at ffmpeg's decode rate (~3x real time).
        if not self._start_wall:
            self._start_wall = time.monotonic()      # anchor on first frame
        sent_frames = self._bytes_sent / RTP_BYTES_PER_FRAME
        ideal_wall = sent_frames / (RTP_SRATE / RTP_SAMPLES_PER_FRAME)
        ahead = ideal_wall - (time.monotonic() - self._start_wall)
        if ahead > 0:
            time.sleep(ahead if ahead < 0.25 else 0.25)

    def _status_cb(self, **kw):
        try:
            self._status_cb(**kw)
        except Exception as e:
            _log.warning("player: status_cb raised: %s", e)
