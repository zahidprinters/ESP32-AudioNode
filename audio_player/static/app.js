"use strict";
// AudioPlayer UI — talks to the Flask backend over REST (fetch) + Socket.IO
// for status push. Seek bar works in 100 ms units (see onStatus/seek).
(function () {
  var STATE = { state: "idle", src: null, volume: 1.0, position_s: 0,
                position_ms: 0, nodes: [], files: [], root: "" };
  var $ = function (id) { return document.getElementById(id); };

  function api(path, body) {
    var opts = { method: body === undefined ? "GET" : "POST" };
    if (body !== undefined) {
      opts.headers = { "Content-Type": "application/json" };
      opts.body = JSON.stringify(body);
    }
    return fetch(path, opts).then(function (r) { return r.json(); });
  }

  // ---- library ----------------------------------------------------------
  function loadLibrary() {
    var root = STATE.root || $("libRoot").value.trim() || "";
    if (!root) {
      $("libInfo").textContent = "No library folder set. Choose one or type a path.";
      return;
    }
    $("libInfo").textContent = "Scanning " + root + " ...";
    api("/api/library?root=" + encodeURIComponent(root))
      .then(function (d) {
        STATE.root = d.root || root;
        STATE.files = d.files || [];
        $("libRoot").value = STATE.root;
        renderFiles();
        if (d.error) { showError(d.error); }
        if (STATE.files.length) {
          $("libInfo").textContent = STATE.files.length + " file(s) in " + STATE.root;
          if (!STATE.src) { selectFile(0); }
        } else {
          $("libInfo").textContent = "No audio files found in " + STATE.root;
        }
      })
      .catch(function (e) { showError("Library scan failed: " + e.message); });
  }

  function renderFiles() {
    var ul = $("fileList");
    ul.innerHTML = "";
    STATE.files.forEach(function (f, i) {
      var li = document.createElement("li");
      if (f.path === STATE.src) { li.className = "sel"; }
      var name = document.createElement("span");
      name.className = "fname";
      name.textContent = f.name;
      var dur = document.createElement("span");
      dur.className = "fdur";
      dur.textContent = f.duration_s != null ? formatS(f.duration_s) : "?";
      var sz = document.createElement("span");
      sz.className = "fsz";
      sz.textContent = fmtBytes(f.size_bytes);
      li.appendChild(name);
      li.appendChild(dur);
      li.appendChild(sz);
      li.addEventListener("click", function () { selectFile(i); });
      ul.appendChild(li);
    });
  }

  function selectFile(i) {
    var f = STATE.files[i];
    if (!f) { return; }
    STATE.src = f.path;
    $("nowSrc").textContent = f.name +
      (f.duration_s != null ? "  -  " + formatS(f.duration_s) : "");
    var dur = f.duration_s || 0;
    $("seekBar").max = Math.max(1000, Math.round(dur * 10));  // 100 ms units
    $("seekBar").value = 0;
    $("posLabel").textContent = "0:00 / " + formatS(dur);
    renderFiles();
  }

  // Folder picker: browsers cannot hand a filesystem path to the server, so
  // we ask the native picker (as a convenience) and require the path text.
  function pickFolder() {
    var apply = function (p) {
      if (p && p.trim()) {
        $("libRoot").value = p.trim();
        STATE.root = p.trim();
        loadLibrary();
      }
    };
    if (!window.showDirectoryPicker) {
      apply(prompt("Full path to your audio folder, e.g. D:\\Music"));
      return;
    }
    window.showDirectoryPicker().then(function () {
      apply(prompt("Enter the full local path to that folder (e.g. D:\\Music)"));
    }).catch(function () { /* user cancelled */ });
  }

  // ---- transport --------------------------------------------------------
  function doPlay() {
    if (!STATE.src) { pickFolder(); return; }
    api("/api/play", { path: STATE.src, volume: STATE.volume })
      .then(function (d) {
        if (d.error) { showError(d.error); }
        else { $("playBtn").textContent = "Playing..."; }
      })
      .catch(function (e) { showError(e.message); });
  }

  function doStop() {
    api("/api/stop", {})
      .then(function () {
        $("playBtn").textContent = "Play";
        $("seekBar").value = 0;
        var f = STATE.files.find(function (x) { return x.path === STATE.src; });
        $("posLabel").textContent = "0:00 / " + formatS((f && f.duration_s) || 0);
      })
      .catch(function (e) { showError(e.message); });
  }

  function setVolume(v) {
    STATE.volume = v;
    api("/api/volume", { volume: v })
      .then(function (d) { if (d.error) { showError(d.error); } })
      .catch(function (e) { showError(e.message); });
  }

  function seek(posMs) {
    api("/api/seek", { position_ms: posMs })
      .then(function (d) { if (d.error) { showError(d.error); } })
      .catch(function (e) { showError(e.message); });
  }

  // ---- status rendering -------------------------------------------------
  function onStatus() {
    $("playBtn").textContent = STATE.state === "playing" ? "Playing..." : "Play";
    var f = STATE.files.find(function (x) { return x.path === STATE.src; });
    var dur = (f && f.duration_s != null) ? f.duration_s : 0;
    $("seekBar").max = Math.max(1000, Math.round(dur * 10));   // 100 ms units
    // Server position is in ms; the slider counts 100 ms steps.
    if (document.activeElement !== $("seekBar")) {
      $("seekBar").value = Math.round((STATE.position_ms || 0) / 100);
    }
    $("posLabel").textContent =
      formatMs(STATE.position_ms) + " / " + formatS(dur);
    renderNodes();
  }

  function renderNodes() {
    var ul = $("nodeList");
    ul.innerHTML = "";
    if (!STATE.nodes.length) {
      $("nodeInfo").textContent = "No nodes configured.";
      return;
    }
    STATE.nodes.forEach(function (n) {
      var li = document.createElement("li");
      li.className = "node" + (n.playing ? " playing" : "");
      var head = document.createElement("div");
      head.className = "nodehead";
      var nm = document.createElement("span");
      nm.className = "nodename";
      nm.textContent = n.name;
      var ip = document.createElement("span");
      ip.className = "nodeip";
      ip.textContent = n.ip + ":" + n.port;
      head.appendChild(nm);
      head.appendChild(ip);
      var body = document.createElement("div");
      body.className = "nodebody";
      var st = document.createElement("span");
      st.className = "nodestat";
      st.textContent = n.playing ? "streaming" : "idle";
      var ps = document.createElement("span");
      ps.className = "nodepos";
      ps.textContent = "pos " + (n.stream_position_s || 0).toFixed(1) + " s";
      body.appendChild(st);
      body.appendChild(ps);
      li.appendChild(head);
      li.appendChild(body);
      ul.appendChild(li);
    });
    var live = STATE.nodes.some(function (n) { return n.playing; });
    $("nodeInfo").textContent = STATE.nodes.length + " node" +
      (STATE.nodes.length > 1 ? "s" : "") + " configured" +
      (live ? " - streaming" : "");
  }

  // ---- helpers ----------------------------------------------------------
  function formatS(s) {
    if (s == null || isNaN(s)) { return "0:00"; }
    s = Math.max(0, Math.floor(s));
    var m = Math.floor(s / 60), sec = s % 60;
    return m + ":" + (sec < 10 ? "0" : "") + sec;
  }

  function formatMs(ms) {
    return formatS((ms == null ? 0 : ms) / 1000);
  }

  function fmtBytes(b) {
    if (!b) { return "-"; }
    if (b > 1048576) { return (b / 1048576).toFixed(1) + " MB"; }
    if (b > 1024) { return (b / 1024).toFixed(1) + " KB"; }
    return b + " B";
  }

  function showError(msg) {
    var box = $("errorBox");
    box.textContent = (msg && msg.message) ? msg.message : String(msg);
    box.hidden = false;
    var text = box.textContent;
    setTimeout(function () {
      if (box.textContent === text) { box.hidden = true; }
    }, 8000);
  }
  // ---- WebSocket status push -------------------------------------------
  var socket = null;

  function connectWS() {
    if (typeof io === "undefined") {
      var s = document.createElement("script");
      s.src = "https://cdn.socket.io/4.7.5/socket.io.min.js";
      s.onload = tryConnect;
      s.onerror = function () { /* no CDN: REST still works */ };
      document.head.appendChild(s);
      return;
    }
    tryConnect();
  }

  function tryConnect() {
    socket = io("/", { reconnection: true, reconnectionDelay: 1000 });
    socket.on("player_status", function (d) {
      if (d.state !== undefined) { STATE.state = d.state; }
      if (d.src !== undefined) { STATE.src = d.src; }
      if (d.volume !== undefined) {
        STATE.volume = d.volume;
        $("volSlider").value = d.volume;
        $("volLabel").textContent = Number(d.volume).toFixed(2);
      }
      if (d.position_s !== undefined) { STATE.position_s = d.position_s; }
      if (d.position_ms !== undefined) { STATE.position_ms = d.position_ms; }
      if (d.nodes !== undefined) { STATE.nodes = d.nodes; }
      if (d.error) { showError(d.error); }
      onStatus();
    });
    socket.on("library_updated", function (d) {
      if (d.root !== undefined) { STATE.root = d.root; }
      if (d.files) {
        STATE.files = d.files;
        $("libRoot").value = STATE.root;
        renderFiles();
        $("libInfo").textContent =
          STATE.files.length + " file(s) in " + STATE.root;
      }
    });
    socket.on("connect", function () {
      $("nodeInfo").textContent = "Connected to server";
    });
    socket.on("disconnect", function () {
      $("nodeInfo").textContent = "Disconnected";
    });
  }

  // ---- wiring -----------------------------------------------------------
  $("playBtn").addEventListener("click", function () {
    if (!STATE.src) { pickFolder(); return; }
    doPlay();
  });
  $("stopBtn").addEventListener("click", doStop);
  $("pickBtn").addEventListener("click", pickFolder);
  $("rescanBtn").addEventListener("click", loadLibrary);
  $("volSlider").addEventListener("input", function () {
    $("volLabel").textContent = parseFloat($("volSlider").value).toFixed(2);
  });
  $("volSlider").addEventListener("change", function () {
    setVolume(parseFloat($("volSlider").value));
  });
  $("seekBar").addEventListener("input", function () {
    // Slider counts 100 ms units -> display as ms.
    $("posLabel").textContent = formatMs(parseInt($("seekBar").value, 10) * 100);
  });
  $("seekBar").addEventListener("change", function () {
    seek(parseInt($("seekBar").value, 10) * 100);
  });
  $("libRoot").addEventListener("change", function () {
    var v = $("libRoot").value.trim();
    if (v) { STATE.root = v; loadLibrary(); }
  });

  // ---- boot -------------------------------------------------------------
  $("libRoot").value = "";
  loadLibrary();
  connectWS();
})();