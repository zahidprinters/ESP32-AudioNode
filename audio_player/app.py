# audio_player — browser-based RTP/UDP audio server for ESP32 AudioNode boards.
#
# Stack (V1): Flask + Flask-SocketIO (eventlet) + ffmpeg via imageio-ffmpeg.
# Run:  python -m audio_player.app        (from d:/esp-idf, or any cwd)
# UI:   http://localhost:5000
#
# The UI talks to this backend two ways:
#   * REST  (fetch)  -> /api/library, /api/play, /api/stop, /api/volume, /api/seek
#   * Socket.IO      -> "player_status" / "library_updated" push, plus the same
#                       commands as events for scripted clients.
#
# Known ceiling: the position loop pushes every 250 ms, so the seek bar and the
# per-node position readout are coarse. Fine for V1 (one node).

import os
import time
import logging
import threading

from audio_player.config import cfg, RTP_SRATE, RTP_PORT
from audio_player.library import scan_library
from audio_player.player import Player

_log = logging.getLogger("audio_player")


def create_app():
    from flask import Flask, render_template, request, jsonify
    from flask_socketio import SocketIO, emit

    app = Flask(__name__, static_folder="static", template_folder="templates")
    socketio = SocketIO(app, async_mode="eventlet", cors_allowed_origins="*")

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
        with status_lock:
            state = status["state"]
            pos_s = status.get("position_s", 0.0)
        return _nodes_for(state, pos_s)

    def _on_player_status(**kw):
        with status_lock:
            for k in ("state", "src", "volume", "error"):
                if k in kw:
                    status[k] = kw[k]
        payload = dict(kw)
        payload["nodes"] = _node_status()
        try:
            socketio.emit("player_status", payload, namespace="/")
        except Exception as e:
            _log.warning("emit player_status failed: %s", e)

    def background_position_loop():
        while True:
            time.sleep(0.25)
            try:
                pos_s = round(player.sample_position / RTP_SRATE, 2)
                pos_ms = int(pos_s * 1000)
                with status_lock:
                    status["position_s"] = pos_s
                    status["position_ms"] = pos_ms
                    state = status["state"]
                # NB: never call _node_status() while holding status_lock.
                # threading.Lock is not reentrant, so nesting it deadlocks the
                # loop *and* every REST request waiting on the same lock.
                nodes = _nodes_for(state, pos_s)
                with status_lock:
                    status["nodes"] = nodes
                socketio.emit("player_status",
                              {"position_s": pos_s, "position_ms": pos_ms,
                               "nodes": nodes}, namespace="/")
            except Exception as e:
                _log.debug("position loop: %s", e)

    player = Player(status_cb=_on_player_status)

    def _status_snapshot():
        with status_lock:
            snap = dict(status)
        snap["nodes"] = _node_status()
        return snap

    # ---- REST routes (the browser UI uses these) --------------------------
    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/status")
    def api_status():
        return jsonify(_status_snapshot())

    @app.route("/api/library")
    def api_library():
        root = request.args.get("root") or cfg.library_root
        if os.path.isdir(root):
            cfg.library_root = root
            return jsonify({"root": root, "files": scan_library(root)})
        return jsonify({"root": root, "files": [],
                        "error": "not a directory: " + str(root)})

    @app.route("/api/play", methods=["POST"])
    def api_play():
        data = request.get_json(silent=True) or {}
        path = data.get("path")
        vol = data.get("volume", cfg.default_volume)
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
        player.stop()
        return jsonify({"ok": True})

    @app.route("/api/volume", methods=["POST"])
    def api_volume():
        data = request.get_json(silent=True) or {}
        try:
            player.set_volume(float(data.get("volume", cfg.default_volume)))
        except Exception as e:
            return jsonify({"error": str(e)}), 400
        return jsonify({"ok": True, "volume": player.volume})

    @app.route("/api/seek", methods=["POST"])
    def api_seek():
        data = request.get_json(silent=True) or {}
        try:
            pos_ms = float(data.get("position_ms", 0))
            player.seek(int(max(0.0, pos_ms / 1000.0) * RTP_SRATE))
        except Exception as e:
            return jsonify({"error": str(e)}), 400
        return jsonify({"ok": True})

    # ---- Socket.IO handlers (same ops, for WS-only clients) --------------
    @socketio.on("play", namespace="/")
    def ws_play(data):
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
        player.stop()

    @socketio.on("set_volume", namespace="/")
    def ws_volume(data):
        data = data or {}
        try:
            player.set_volume(float(data.get("volume", cfg.default_volume)))
        except Exception as e:
            emit("error", {"message": str(e)})

    @socketio.on("seek", namespace="/")
    def ws_seek(data):
        data = data or {}
        try:
            pos_ms = float(data.get("position_ms", 0))
            player.seek(int(max(0.0, pos_ms / 1000.0) * RTP_SRATE))
        except Exception as e:
            emit("error", {"message": str(e)})

    @socketio.on("set_library_root", namespace="/")
    def ws_set_library_root(data):
        root = str((data or {}).get("root", ""))
        if os.path.isdir(root):
            cfg.library_root = root
            emit("library_updated", {"root": root, "files": scan_library(root)})
        else:
            emit("error", {"message": "library root not found: " + root})

    @socketio.on("get_status", namespace="/")
    def ws_get_status(_data=None):
        emit("player_status", _status_snapshot())

    threading.Thread(target=background_position_loop, name="pos-loop",
                     daemon=True).start()
    return app, socketio, player


def main():
    import argparse
    ap = argparse.ArgumentParser(
        description="audio_player — browser RTP/UDP audio server for ESP32 nodes")
    ap.add_argument("--host", default=cfg.host, help="HTTP bind address")
    ap.add_argument("--port", type=int, default=cfg.port, help="HTTP port")
    ap.add_argument("--library", help="default library root (UI can change it)")
    ap.add_argument("--node", action="append", metavar="IP[:PORT]",
                    help="replace the node list (repeatable); default = config.py")
    args = ap.parse_args()

    if args.library:
        cfg.library_root = args.library
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
    socketio.run(app, host=cfg.host, port=cfg.port, log_output=False)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    main()