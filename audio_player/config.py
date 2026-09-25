# audio_player config — single place for defaults
# Board IPs, library root, HTTP/WS host:port, RTP constants delegate to player.py.

import json
import os
import threading
from pathlib import Path

# ---------------------------------------------------------------------------
# RTP constants (MUST match firmware ARCHITECTURE.md protocol spec)
# ---------------------------------------------------------------------------
RTP_SRATE              = 48000          # Hz
RTP_FRAME_MS           = 20
RTP_SAMPLES_PER_FRAME  = 960            # = SRATE * FRAME_MS / 1000
RTP_BYTES_PER_FRAME    = 1920           # = SAMPLES_PER_FRAME * 2 (16-bit mono)
RTP_PT                 = 96             # dynamic L16/48k/mono
RTP_PORT               = 1234           # board listener port

# Espressif Systems MAC OUI prefixes — used to spot ESP32 boards when reading
# the ARP table after a subnet ping sweep (node discovery in app.py).
ESPRESSIF_OUIS = ("5C-01-9B", "5C-01-99", "24-6F-28", "24-0A-C4",
                  "30-AE-A4", "30-AE-5A", "84-CC-A8", "84-F7-03",
                  "8C-AA-B5", "A4-CF-12", "A4-CF-13", "A0-DD-6C",
                  "48-27-E2", "68-B6-B3", "7C-DF-A1", "DC-54-75",
                  "54-32-04", "10-52-1C", "C8-2B-96", "C4-4B-ED",
                  "4C-11-AE", "34-85-18", "34-98-7A", "58-BF-25",
                  "B0-A7-32", "EC-64-C9", "F4-12-FA", "FC-F5-C4",
                  # 30-30-F9 = ESP32-S3-DevKitC-1 (this project's board family)
                  "30-30-F9")

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
# Equalizer — VLC-style 10-band peaking EQ, live-adjustable from the UI.
# ---------------------------------------------------------------------------
# VLC's exact band centers (Adjustments and Effects -> Equalizer), Hz.
EQ_BANDS = [60, 170, 310, 600, 1000, 3000, 6000, 12000, 14000, 16000]
EQ_MIN_DB, EQ_MAX_DB = -12.0, 12.0

# Built-in presets (name -> 10 band gains, dB on VLC's grid: 60/170/310/600 Hz,
# 1/3/6/12/14/16 kHz). Common media-player set (VLC/Winamp-style) plus two
# hardware-specific ones: "Mid Cut (speaker)" encodes the measured speaker
# response (250 Hz-1 kHz distorts first on this driver). Built-ins cannot be
# overwritten.
EQ_BUILTIN_PRESETS = {
    "Flat":              [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "Acoustic":          [4, 3, 2, 0, -2, -1, 1, 2, 3, 4],
    "Bass Booster":      [8, 7, 5, 3, 1, 0, 0, 0, 0, 0],
    "Bass Reducer":      [-8, -7, -5, -3, -1, 0, 0, 0, 0, 0],
    "Classical":         [0, 0, 0, 0, 0, 0, -3, -3, -3, -4],
    "Pop":               [2, 2, 0, -1, -1, 0, 1, 2, 2, 0],
    "Rock / Metal":      [5, 4, 2, 0, -2, -1, 2, 3, 4, 4],
    "Vocal / Voice":     [-3, -2, 0, 2, 4, 4, 2, 0, -1, -2],
    "Treble Boost":      [0, 0, 0, 0, 1, 3, 4, 4, 5, 5],
    "Mid Cut (speaker)": [0, -2, -4, -5, -4, -1, 0, 0, 0, 0],
}


class Config:
    """Per-session config. V1 = one node; V2+ appends more.

    ``library_root`` is a directory the UI picker sets at runtime (V1 default
    points at the repo's shipped ``media/`` folder).
    """
    def __init__(self):
        # One node now (V1). Each entry: ip, port, name. The address below is a
        # documented placeholder — set your board's LAN IP in the Nodes tab. It
        # is then persisted to the gitignored nodes.json, which overrides this.
        self.nodes = [
            {"ip": "192.168.1.50", "port": RTP_PORT, "name": "node-1"},
        ]
        # Default library root = the repo's media/ folder. Created on import so a
        # fresh clone works immediately without shipping any audio in git.
        self.library_root = str(Path(__file__).resolve().parent / "media")
        os.makedirs(self.library_root, exist_ok=True)
        self.default_volume = 1.0
        # Measured speaker calibration (tone ladder, 2026-09-15): bass tones
        # CLEAN, mids (250-1k) distort first, song sub-bass peak at 41 Hz is
        # unreproducible, and the board's x2 digital gain saturates above
        # 0.5 FS sender level.
        self.sub_hp_hz = 65.0        # highpass: cut what the driver can't reproduce
        self.bass_cut_hz = 120.0     # gentle shelf (-6@150 over-corrected)
        self.bass_cut_db = -3.0
        self.dac_ceiling = 0.5       # alimiter ceiling: sender 0.5 x2 = full-scale DAC
        # HTTP + WS
        self.host = "0.0.0.0"
        self.port = 5000
        # Equalizer state (UI: /api/eq). Disabled by default so the measured
        # speaker-calibration chain is unchanged until the user turns EQ on.
        self.eq_enabled = False
        self.eq_preamp_db = 0.0
        self.eq_gains = [0.0] * len(EQ_BANDS)
        # User-saved presets (built-ins are hardcoded above).
        self.eq_user_presets = {}
        self.eq_presets_path = str(Path(__file__).resolve().parent /
                                   "eq_presets.json")
        # Node list persistence (discovered/added nodes survive restarts).
        self.nodes_path = str(Path(__file__).resolve().parent / "nodes.json")
        # Settings: max volume ceiling, default EQ preset, default library root.
        # Persisted to settings.json (gitignored user state).
        self.settings_path = str(Path(__file__).resolve().parent / "settings.json")
        self.max_volume = 1.0
        self.default_eq_preset = "Mid Cut (speaker)"
        self.default_library_root = None
        # Scheduled play/stop plans: each plan = {"id": int, "time": "HH:MM",
        # "action": "play"|"stop", "file": "filepath (relative to library_root)"}.
        # Persisted inside settings.json; survives restarts.
        self.scheduled_plans = []

cfg = Config()


def node_save():
    """Persist cfg.nodes (write-then-replace, small file)."""
    data = {"nodes": [{"ip": str(n["ip"]), "port": int(n["port"]),
                       "name": str(n.get("name", "node"))}
                      for n in cfg.nodes]}
    tmp = cfg.nodes_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, cfg.nodes_path)


def node_load(path=None):
    """Replace cfg.nodes with the persisted list; missing/bad file = keep default."""
    p = path or cfg.nodes_path
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return
    nodes = []
    for n in (d.get("nodes") or []):
        try:
            ip, port = str(n["ip"]), int(n["port"])
            if not (1 <= port <= 65535) or len(nodes) >= 16:
                continue
            nodes.append({"ip": ip, "port": port,
                          "name": str(n.get("name", "node"))})
        except (KeyError, TypeError, ValueError):
            continue
    if nodes:
        cfg.nodes = nodes


node_load()


def eq_save(path=None):
    """Persist current EQ state + user presets (write-then-replace, small file)."""
    p = path or cfg.eq_presets_path
    data = {
        "current": {"enabled": cfg.eq_enabled,
                    "preamp_db": round(cfg.eq_preamp_db, 2),
                    "gains": [round(g, 2) for g in cfg.eq_gains]},
        "presets": {name: {"preamp_db": round(float(v.get("preamp_db", 0.0)), 2),
                           "gains": [round(float(g), 2) for g in v["gains"]]}
                    for name, v in cfg.eq_user_presets.items()},
    }
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, p)


def eq_load(path=None):
    """Apply persisted EQ state to cfg. Missing/corrupt file = keep defaults."""
    p = path or cfg.eq_presets_path
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return
    cur = d.get("current") or {}
    cfg.eq_enabled = bool(cur.get("enabled", False))
    cfg.eq_preamp_db = max(EQ_MIN_DB, min(EQ_MAX_DB, float(cur.get("preamp_db", 0.0))))
    g = cur.get("gains")
    if isinstance(g, list) and len(g) == len(EQ_BANDS):
        cfg.eq_gains = [max(EQ_MIN_DB, min(EQ_MAX_DB, float(x))) for x in g]
    pr = d.get("presets")
    if isinstance(pr, dict):
        cfg.eq_user_presets = {str(k): v for k, v in pr.items()
                               if isinstance(v, dict) and
                               isinstance(v.get("gains"), list) and
                               len(v["gains"]) == len(EQ_BANDS)}


eq_load()


def settings_save():
    """Persist user settings (max_volume, default_eq_preset, default_library_root,
    scheduled_plans)."""
    data = {"max_volume": cfg.max_volume,
            "default_eq_preset": cfg.default_eq_preset,
            "default_library_root": cfg.default_library_root,
            "scheduled_plans": cfg.scheduled_plans}
    tmp = cfg.settings_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, cfg.settings_path)


def settings_load():
    """Load user settings. Missing/corrupt = keep defaults."""
    try:
        with open(cfg.settings_path, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return
    if "max_volume" in d:
        cfg.max_volume = max(0.0, min(10.0, float(d["max_volume"])))
    if "default_eq_preset" in d:
        cfg.default_eq_preset = str(d["default_eq_preset"])
    if "default_library_root" in d:
        cfg.default_library_root = str(d["default_library_root"]) \
            if d["default_library_root"] else None
    if "scheduled_plans" in d:
        plans = d["scheduled_plans"]
        if isinstance(plans, list):
            cfg.scheduled_plans = plans


settings_load()
