# audio_player — browser-based RTP/UDP audio server for ESP32 AudioNode boards.
#
# Stack: Flask + Flask-SocketIO in threading mode (no eventlet) + ffmpeg via
# imageio-ffmpeg. Dependencies are verified by audio_player/deps.py before
# anything else starts, so a fresh machine is told what to install instead of
# failing on an ImportError.
# Run:  python -m audio_player.app        (from the repository root)
# UI:   http://localhost:5000
#
# The UI talks to this backend two ways:
#   * REST  (fetch)  -> /api/library, /api/play, /api/stop, /api/volume, /api/seek
#   * Socket.IO      -> "player_status" / "library_updated" push, plus the same
#                       commands as events for scripted clients.
#
# Known ceiling: the position loop pushes every 250 ms, so the seek bar and the
# per-node position readout are coarse. Fine for V1 (one node).

import datetime
import os
import re
import sys
import time
import socket
import logging
import threading
import subprocess

from audio_player import deps
from audio_player.config import (cfg, RTP_SRATE, RTP_PORT, EQ_BANDS,
                                 EQ_MIN_DB, EQ_MAX_DB, EQ_BUILTIN_PRESETS,
                                 eq_save, node_save, node_load, eq_load,
                                 settings_load, settings_save, ESPRESSIF_OUIS)
from audio_player.library import scan_library
from audio_player.player import Player

_log = logging.getLogger("audio_player")


def _setup_file_log():
    """Send our own messages to logs/app.log as well as the console.

    Deliberately not the root logger: that would also capture werkzeug's
    per-request access log and the file would grow without bound.
    """
    path = deps.log_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(path, encoding="utf-8")
        fh.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logging.getLogger("audio_player").addHandler(fh)
    except OSError as e:
        _log.warning("file logging disabled (%s): %s", path, e)


def create_app():
    """Build the Flask app, routes, WebSocket handlers and background threads.
        Returns (app, socketio, player). All persisted state is loaded here,
        before the routes are built."""
    from flask import Flask, render_template, request, jsonify
    from flask_socketio import SocketIO, emit

    app = Flask(__name__, static_folder="static", template_folder="templates")
    socketio = SocketIO(app, async_mode="threading", cors_allowed_origins="*")

    # ---- boot: load persisted user state (nodes, EQ, settings, schedules) ----
    # Saving worked but nothing ever LOADED these files — restarts lost nodes,
    # EQ curve, settings and schedule plans. Load them all here, before the
    # routes are built.
    node_load()
    eq_load()
    settings_load()
    # A --library CLI argument wins over the saved default library root.
    if cfg.default_library_root and not getattr(cfg, "library_from_arg", False):
        cfg.library_root = cfg.default_library_root
    # Apply the default EQ preset from Settings at boot ("default EQ profile").
    preset = (EQ_BUILTIN_PRESETS.get(cfg.default_eq_preset)
              or cfg.eq_user_presets.get(cfg.default_eq_preset))
    if isinstance(preset, list):            # built-ins are gains-only lists
        preset = {"preamp_db": 0.0, "gains": preset}
    if preset:
        cfg.eq_enabled = True
        cfg.eq_preamp_db = float(preset.get("preamp_db", 0.0))
        cfg.eq_gains = list(preset["gains"])

    status = {"state": "idle", "src": None, "volume": cfg.default_volume,
              "position_s": 0.0, "position_ms": 0, "nodes": [], "error": None}
    status_lock = threading.Lock()
    player = None

    def _nodes_for(state, pos_s):
        """Node view for a given playback state/position (takes no locks)."""
        running = state == "playing"
        return [{"name": n.get("name", "node"), "ip": n["ip"], "port": n["port"],
                 "connected": running, "playing": running,
                 "stream_position_s": round(pos_s, 2)}
                for n in cfg.nodes]

    def _node_status():
        """Node view for the API. Returns a list of node dicts; holds the lock only
            long enough to read the state it needs."""
        with status_lock:
            state = status["state"]
            pos_s = status.get("position_s", 0.0)
        return _nodes_for(state, pos_s)

    def _on_player_status(**kw):
        """Player callback: fold a state change into the status dict and push it to
            every connected browser. Returns nothing."""
        with status_lock:
            for k in ("state", "src", "volume", "error", "eq", "src_path"):
                if k in kw:
                    status[k] = kw[k]
        payload = dict(kw)
        payload["nodes"] = _node_status()
        try:
            socketio.emit("player_status", payload, namespace="/")
        except Exception as e:
            _log.warning("emit player_status failed: %s", e)

    def background_position_loop():
        """Thread: republish playback position 4x/second and refresh the per-node
            readout. Returns nothing; runs until the process ends."""
        while True:
            time.sleep(0.25)
            try:
                pos_s = round(player.sample_position / RTP_SRATE, 2)
                pos_ms = int(pos_s * 1000)
                with status_lock:
                    status["position_s"] = pos_s
                    status["position_ms"] = pos_ms
                    state = status["state"]
                    src = status.get("src")
                # NB: never call _node_status() while holding status_lock.
                # threading.Lock is not reentrant, so nesting it deadlocks the
                # loop *and* every REST request waiting on the same lock.
                nodes = _nodes_for(state, pos_s)
                with status_lock:
                    status["nodes"] = nodes
                # state/src ride along so a client that (re)connects between
                # play/stop pushes still gets the current state (self-healing).
                socketio.emit("player_status",
                              {"state": state, "src": src,
                               "position_s": pos_s, "position_ms": pos_ms,
                               "nodes": nodes}, namespace="/")
            except Exception as e:
                _log.debug("position loop: %s", e)

    player = Player(status_cb=_on_player_status)

    def _status_snapshot():
        """What /api/status returns: a copy of the status dict plus the node view.
            Never holds a lock while building the node list."""
        with status_lock:
            snap = dict(status)
        snap["nodes"] = _node_status()
        return snap

    # ---- REST routes (the browser UI uses these) --------------------------
    @app.route("/")
    def index():
        """GET / -> the single-page UI. Returns the rendered template."""
        return render_template("index.html")

    @app.route("/api/status")
    def api_status():
        """GET /api/status -> state, position, volume, nodes and EQ as JSON."""
        return jsonify(_status_snapshot())

    @app.route("/api/library")
    def api_library():
        """GET /api/library?root=DIR -> scan DIR recursively for audio files and adopt
            it as the library root. Returns {root, files[]}, with {error} set when
            the path is not a directory."""
        root = request.args.get("root") or cfg.library_root
        if os.path.isdir(root):
            cfg.library_root = root
            return jsonify({"root": root, "files": scan_library(root)})
        return jsonify({"root": root, "files": [],
                        "error": "not a directory: " + str(root)})

    @app.route("/api/play", methods=["POST"])
    def api_play():
        """POST /api/play {path, volume?} -> start playback, or resume if paused on the
            same file. Returns {ok, src}, or 400 {error}."""
        data = request.get_json(silent=True) or {}
        path = data.get("path")
        vol = min(cfg.max_volume, float(data.get("volume", cfg.default_volume)))
        if not path:
            return jsonify({"error": "path required"}), 400
        try:
            player.play(path, volume=float(vol))
        except Exception as e:
            _log.error("play failed: %s", e)
            return jsonify({"error": str(e)}), 400
        return jsonify({"ok": True, "src": os.path.basename(str(path))})

    @app.route("/api/stop", methods=["POST"])
    def api_stop():
        """POST /api/stop -> stop the stream. Returns {ok}."""
        player.stop()
        return jsonify({"ok": True})

    @app.route("/api/volume", methods=["POST"])
    def api_volume():
        """POST /api/volume {volume} -> set volume, clamped to the configured maximum.
            Returns {ok, volume} or 400 {error}."""
        data = request.get_json(silent=True) or {}
        try:
            player.set_volume(min(cfg.max_volume,
                                  float(data.get("volume", cfg.default_volume))))
        except Exception as e:
            return jsonify({"error": str(e)}), 400
        return jsonify({"ok": True, "volume": player.volume})

    @app.route("/api/seek", methods=["POST"])
    def api_seek():
        """POST /api/seek {position_ms} -> restart the pipeline there. Returns
            {ok, position_ms} or 400 {error}."""
        data = request.get_json(silent=True) or {}
        try:
            pos_ms = float(data.get("position_ms", 0))
            player.seek(int(max(0.0, pos_ms / 1000.0) * RTP_SRATE))
        except Exception as e:
            return jsonify({"error": str(e)}), 400
        return jsonify({"ok": True})

    # ---- Equalizer (VLC-style 10-band; live-applied by player.set_eq) -----
    def _eq_view():
        """The EQ dict the API returns: enabled flag, preamp, band gains, limits."""
        return {"enabled": cfg.eq_enabled, "preamp_db": cfg.eq_preamp_db,
                "gains": list(cfg.eq_gains)}

    def _preset_names():
        """Sorted names of every available preset, built-in and user alike."""
        return sorted(set(EQ_BUILTIN_PRESETS) | set(cfg.eq_user_presets))

    @app.route("/api/eq", methods=["GET"])
    def api_eq_get():
        """GET /api/eq -> current EQ state, band limits and preset names."""
        return jsonify({"enabled": cfg.eq_enabled,
                        "preamp_db": cfg.eq_preamp_db, "gains": cfg.eq_gains,
                        "bands": EQ_BANDS, "min_db": EQ_MIN_DB,
                        "max_db": EQ_MAX_DB, "presets": _preset_names()})

    @app.route("/api/eq", methods=["POST"])
    def api_eq_set():
        """POST /api/eq {enabled, preamp_db, gains[10]} -> clamp, persist and apply
            live. Returns {ok, eq}, or 400 {error} on a wrong band count."""
        data = request.get_json(silent=True) or {}
        try:
            player.set_eq(enabled=data.get("enabled"),
                          preamp_db=data.get("preamp_db"),
                          gains=data.get("gains"))
        except Exception as e:
            return jsonify({"error": str(e)}), 400
        return jsonify({"ok": True, "eq": _eq_view()})

    @app.route("/api/eq/preset", methods=["POST"])
    def api_eq_apply_preset():
        """POST /api/eq/preset {name} -> apply a built-in or user preset. Returns
            {ok, eq}, or 400 {error} for an unknown name."""
        name = str((request.get_json(silent=True) or {}).get("name", ""))
        preset = EQ_BUILTIN_PRESETS.get(name) or cfg.eq_user_presets.get(name)
        if preset is None:
            return jsonify({"error": "no preset named %r" % name}), 404
        if isinstance(preset, list):        # built-ins are gains-only lists
            preset = {"preamp_db": 0.0, "gains": preset}
        try:
            player.set_eq(enabled=True,
                          preamp_db=float(preset.get("preamp_db", 0.0)),
                          gains=preset["gains"])
        except Exception as e:
            return jsonify({"error": str(e)}), 400
        return jsonify({"ok": True, "eq": _eq_view()})

    @app.route("/api/eq/presets", methods=["POST"])
    def api_eq_save_preset():
        """POST /api/eq/presets {name} -> store the current curve under a name.
            Returns {ok, presets}; refuses to overwrite a built-in."""
        data = request.get_json(silent=True) or {}
        name = str(data.get("name", "")).strip()
        if not name:
            return jsonify({"error": "name required"}), 400
        if name in EQ_BUILTIN_PRESETS:
            return jsonify({"error": "built-in preset '%s' cannot be "
                                      "overwritten" % name}), 400
        cfg.eq_user_presets[name] = {"preamp_db": cfg.eq_preamp_db,
                                     "gains": list(cfg.eq_gains)}
        eq_save()
        return jsonify({"ok": True, "presets": _preset_names()})

    # ---- Pause / resume / user settings -------------------------------------
    @app.route("/api/pause", methods=["POST"])
    def api_pause():
        """POST /api/pause -> stop the pipeline, keep the position. Returns {ok}."""
        player.pause()
        return jsonify({"ok": True})

    @app.route("/api/resume", methods=["POST"])
    def api_resume():
        """POST /api/resume -> continue from the paused position. Returns {ok}."""
        player.resume()
        return jsonify({"ok": True})

    @app.route("/api/settings", methods=["GET"])
    def api_settings_get():
        """GET /api/settings -> max volume, default EQ preset, default library root."""
        return jsonify({"ok": True, "settings": {
            "max_volume": cfg.max_volume,
            "default_eq_preset": cfg.default_eq_preset,
            "default_library_root": cfg.default_library_root}})

    @app.route("/api/settings", methods=["POST"])
    def api_settings_set():
        """POST /api/settings -> change any subset, persist, and return the same payload
            as the GET."""
        data = request.get_json(silent=True) or {}
        if "max_volume" in data:
            cfg.max_volume = max(0.0, min(10.0, float(data["max_volume"])))
        if "default_eq_preset" in data:
            cfg.default_eq_preset = str(data["default_eq_preset"])
        if "default_library_root" in data:
            root = str(data["default_library_root"])
            cfg.default_library_root = root if root else None
        settings_save()
        return api_settings_get()

    # ---- Scheduled play/stop -----------------------------------------------
    next_id = [0]

    def _plans_from_body(data):
        """Validate a plan from request body; returns (plan, error_str)."""
        name = str((data or {}).get("name", "")).strip()
        action = str((data or {}).get("action", "")).strip().lower()
        file_ = str((data or {}).get("file", "")).strip()
        time_ = str((data or {}).get("time", "")).strip()
        if not name:
            return None, "name required"
        if action not in ("play", "stop"):
            return None, "action must be 'play' or 'stop'"
        if not file_:
            return None, "file required"
        if not re.fullmatch(r"\d{1,2}:\d{2}", time_):
            return None, "time must be HH:MM (24h), e.g. 07:30"
        hh, mm = time_.split(":")
        if not (0 <= int(hh) <= 23 and 0 <= int(mm) <= 59):
            return None, "time out of range (00:00 – 23:59)"
        return {"id": None, "name": name, "action": action,
                "file": file_, "time": "%02d:%02d" % (int(hh), int(mm))}, None

    @app.route("/api/schedule", methods=["GET"])
    def api_schedule_get():
        """GET /api/schedule -> every scheduled play/stop plan."""
        return jsonify({"plans": cfg.scheduled_plans})

    @app.route("/api/schedule", methods=["POST"])
    def api_schedule_add():
        """POST /api/schedule {name, action, file, time} -> validate and add a plan,
            persisted in settings.json. Returns {ok, plans} or 400 {error}."""
        data = request.get_json(silent=True) or {}
        plan, err = _plans_from_body(data)
        if err:
            return jsonify({"error": err}), 400
        plan["id"] = next_id[0]
        next_id[0] += 1
        cfg.scheduled_plans.append(plan)
        settings_save()
        return jsonify({"ok": True, "plans": cfg.scheduled_plans})

    @app.route("/api/schedule/<int:pid>", methods=["DELETE"])
    def api_schedule_remove(pid):
        """DELETE /api/schedule/<id> -> drop one plan. Returns {ok, plans}, or 404 if no
            plan has that id."""
        kept = [p for p in cfg.scheduled_plans if p["id"] != pid]
        if len(kept) == len(cfg.scheduled_plans):
            return jsonify({"error": "no plan with id %d" % pid}), 404
        cfg.scheduled_plans = kept
        settings_save()
        return jsonify({"ok": True, "plans": cfg.scheduled_plans})

    # ---- Node management + discovery --------------------------------------
    # The board is a UDP *listener*; there is no board->server packet to sniff,
    # so "discovery" = find Espressif MACs on the LAN: ping-sweep the /24 the
    # server PC sits in (lwIP answers ICMP), then read the Windows ARP table
    # and keep OUIs belonging to Espressif. Bounded: 2 rounds of 60 hosts.
    def _local_net():
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("192.168.1.1", 9))  # no traffic sent (UDP connect)
            ip = s.getsockname()[0]
        except Exception:
            return None
        finally:
            s.close()
        m = re.match(r"^(\d+\.\d+\.\d+)\.\d+$", ip)
        return m.group(1) if m else None

    def _arp_entries():
        try:
            out = subprocess.run(["arp", "-a"], capture_output=True, text=True,
                                 timeout=10).stdout
        except Exception:
            return []
        macs = {}
        for line in out.splitlines():
            mm = re.findall(r"(\d+\.\d+\.\d+\.\d+)\s+((?:[0-9a-f]{2}-){5}[0-9a-f]{2})",
                            line, re.I)
            for ip, mac in mm:
                macs[ip] = mac.upper().replace(":", "-")
        return sorted(macs.items())

    def discover_nodes():
        """Find boards on the LAN: ping-sweep the local /24, then keep hosts whose
            MAC OUI belongs to Espressif. The board is a UDP listener, so there is
            no packet of its own to sniff. Returns {subnet, found[],
            configured[]} or {error}. Bounded, ~10 s."""
        base = _local_net()
        if not base:
            return {"error": "could not determine the server's subnet"}
        # Sweep 1..254 in chunks of ~64 concurrent pings (254 ping.exe at once
        # would be heavy; 64 keeps it bounded and the whole sweep < ~10 s).
        lo = 1
        while lo <= 254:
            hi = min(lo + 63, 254)
            procs = []
            for i in range(lo, hi + 1):
                procs.append(subprocess.Popen(
                    ["ping", "-n", "1", "-w", "400", "%s.%d" % (base, i)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)))
            for p in procs:
                try:
                    p.wait(timeout=2)
                except Exception:
                    p.kill()
            lo = hi + 1
        found = []
        for ip, mac in _arp_entries():
            if not ip.startswith(base + "."):
                continue
            oui = mac[:8]
            if any(oui == o.replace(":", "-") for o in ESPRESSIF_OUIS):
                found.append(ip)
        configured = {n["ip"] for n in cfg.nodes}
        return {"subnet": base + ".0/24", "found": found,
                "configured": sorted(configured)}

    @app.route("/api/nodes", methods=["GET"])
    def api_nodes_get():
        """GET /api/nodes -> the configured boards."""
        return jsonify({"nodes": cfg.nodes})

    @app.route("/api/nodes", methods=["POST"])
    def api_nodes_add():
        """POST /api/nodes {ip, port?, name?} -> add or update a board and persist
            the list. Returns {ok, nodes} or 400 {error}."""
        data = request.get_json(silent=True) or {}
        ip = str(data.get("ip", "")).strip()
        port = int(data.get("port", RTP_PORT))
        name = str(data.get("name", "")).strip()
        if not re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip):
            return jsonify({"error": "valid IPv4 required"}), 400
        if not (1 <= port <= 65535):
            return jsonify({"error": "port out of range"}), 400
        if any(n["ip"] == ip for n in cfg.nodes):
            return jsonify({"error": "node %s already configured" % ip}), 400
        if len(cfg.nodes) >= 16:
            return jsonify({"error": "node limit (16) reached"}), 400
        cfg.nodes.append({"ip": ip, "port": port,
                          "name": name or ("node-%d" % (len(cfg.nodes) + 1))})
        node_save()
        _log.info("nodes: added %s:%d (%s)", ip, port, name)
        return jsonify({"ok": True, "nodes": cfg.nodes})

    @app.route("/api/nodes/remove", methods=["POST"])
    def api_nodes_remove():
        """POST /api/nodes/remove {ip} -> drop a board. Returns {ok, nodes}, 404 when
            unknown, or 400 when it would remove the last node."""
        data = request.get_json(silent=True) or {}
        ip = str(data.get("ip", "")).strip()
        before = len(cfg.nodes)
        cfg.nodes = [n for n in cfg.nodes if n["ip"] != ip]
        if len(cfg.nodes) == before:
            return jsonify({"error": "no node with ip %s" % ip}), 404
        if not cfg.nodes:
            return jsonify({"error": "cannot remove the last node"}), 400
        node_save()
        _log.info("nodes: removed %s", ip)
        return jsonify({"ok": True, "nodes": cfg.nodes})

    @app.route("/api/nodes/discover", methods=["POST"])
    def api_nodes_discover():
        """POST /api/nodes/discover -> run discover_nodes()."""
        return jsonify(discover_nodes())

    # ---- Socket.IO handlers (same ops, for WS-only clients) --------------
    @socketio.on("play", namespace="/")
    def ws_play(data):
        """WebSocket "play" -> as /api/play; failures come back as an "error" event.
            Returns nothing."""
        data = data or {}
        path = data.get("path") or data.get("file")
        if not path:
            emit("error", {"message": "path required"})
            return
        try:
            player.play(path, volume=float(data.get("volume", cfg.default_volume)))
        except Exception as e:
            emit("error", {"message": str(e)})

    @socketio.on("stop", namespace="/")
    def ws_stop(_data=None):
        """WebSocket "stop" -> stop the stream. Returns nothing."""
        player.stop()

    @socketio.on("set_volume", namespace="/")
    def ws_volume(data):
        """WebSocket "set_volume" {volume} -> set the volume. Returns nothing."""
        data = data or {}
        try:
            player.set_volume(float(data.get("volume", cfg.default_volume)))
        except Exception as e:
            emit("error", {"message": str(e)})

    @socketio.on("seek", namespace="/")
    def ws_seek(data):
        """WebSocket "seek" {position_ms} -> seek. Returns nothing."""
        data = data or {}
        try:
            pos_ms = float(data.get("position_ms", 0))
            player.seek(int(max(0.0, pos_ms / 1000.0) * RTP_SRATE))
        except Exception as e:
            emit("error", {"message": str(e)})

    @socketio.on("set_library_root", namespace="/")
    def ws_set_library_root(data):
        """WebSocket "set_library_root" {root} -> adopt a folder and broadcast
            "library_updated". Returns nothing."""
        root = str((data or {}).get("root", ""))
        if os.path.isdir(root):
            cfg.library_root = root
            emit("library_updated", {"root": root, "files": scan_library(root)})
        else:
            emit("error", {"message": "library root not found: " + root})

    @socketio.on("get_status", namespace="/")
    def ws_get_status(_data=None):
        """WebSocket "get_status" -> emit the full status snapshot to the caller."""
        emit("player_status", _status_snapshot())

    threading.Thread(target=background_position_loop, name="pos-loop",
                     daemon=True).start()
    # Background ticker: push player_status once a second so the browser
    # seek bar / footer position track playback (state-change pushes alone
    # leave the position frozen between events).
    def background_status_tick():
        """Thread: re-emit the full status once a second so a client that connected
            between events still sees live state. Returns nothing."""
        while True:
            time.sleep(1)
            try:
                socketio.emit("player_status", _status_snapshot(), namespace="/")
            except Exception:
                pass

    threading.Thread(target=background_status_tick, name="status-tick",
                     daemon=True).start()

    # Background scheduler: check every second and fire scheduled play/stop at
    # the right wall-clock time. Plans persist across restarts.
    def background_schedule_loop():
        """Thread: once a second, fire any scheduled play/stop whose local wall-clock
            time has just arrived; broadcast the plan list when something
            fired. Returns nothing."""
        while True:
            time.sleep(1)
            now = datetime.datetime.now()
            hhmm = now.strftime("%H:%M")
            fired = False
            for plan in list(cfg.scheduled_plans):
                if plan["time"] != hhmm:
                    continue
                # Don't double-fire within the same minute (loop runs every 1 s).
                if plan.get("_last_fire") == hhmm:
                    continue
                plan["_last_fire"] = hhmm
                _log.info("schedule: firing plan %r at %s", plan["name"], hhmm)
                fired = True
                try:
                    if player is None:
                        _log.warning("schedule: no player yet, skipping %r",
                                     plan["name"])
                        continue
                    if plan["action"] == "stop":
                        player.stop()
                    elif plan["action"] == "play":
                        file_path = os.path.join(cfg.library_root, plan["file"])
                        if not os.path.isfile(file_path):
                            _log.warning("schedule: file not found %s",
                                         file_path)
                            continue
                        player.play(file_path,
                                    volume=min(cfg.max_volume,
                                               float(cfg.default_volume)))
                except Exception as e:
                    _log.warning("schedule: plan %r failed: %s",
                                 plan["name"], e)
            if fired:
                try:
                    socketio.emit("schedule_updated",
                                  {"plans": cfg.scheduled_plans},
                                  namespace="/")
                except Exception:
                    pass

    threading.Thread(target=background_schedule_loop, name="schedule-loop",
                     daemon=True).start()
    return app, socketio, player


def main():
    """CLI entry point: verify dependencies, build the app, serve it. Exits 1 if the
        required packages are missing. Does not return otherwise."""
    import argparse
    ap = argparse.ArgumentParser(
        description="audio_player — browser RTP/UDP audio server for ESP32 nodes")
    ap.add_argument("--host", default=cfg.host, help="HTTP bind address")
    ap.add_argument("--port", type=int, default=cfg.port, help="HTTP port")
    ap.add_argument("--library", help="default library root (UI can change it)")
    ap.add_argument("--node", action="append", metavar="IP[:PORT]",
                    help="replace the node list (repeatable); default = config.py")
    ap.add_argument("--install-deps", action="store_true",
                    help="install the required Python packages into this "
                         "interpreter and exit")
    args = ap.parse_args()

    if args.install_deps:
        sys.exit(0 if deps.install() else 1)
    # Verify the packages before anything else, on every entry point - not
    # just the Windows launcher - so a fresh machine gets one clear message
    # instead of a ModuleNotFoundError from inside the server.
    if not deps.ensure():
        sys.exit(1)
    _setup_file_log()

    if args.library:
        cfg.library_root = args.library
        cfg.library_from_arg = True      # beats settings.json default root
    if args.node:
        cfg.nodes = []
        for spec in args.node:
            ip, _, port = spec.partition(":")
            cfg.nodes.append({"ip": ip, "port": int(port or RTP_PORT),
                              "name": "node-%d" % (len(cfg.nodes) + 1)})

    app, socketio, player = create_app()
    _log.info("audio_player: library_root=%s", cfg.library_root)
    _log.info("audio_player: nodes=%s", [n["ip"] for n in cfg.nodes])
    _log.info("audio_player: UI at http://localhost:%d", cfg.port)
    socketio.run(app, host=cfg.host, port=cfg.port, log_output=False, allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    main()