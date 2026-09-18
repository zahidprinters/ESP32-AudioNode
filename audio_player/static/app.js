"use strict";
// AudioPlayer UI — talks to the Flask backend over REST (fetch) + Socket.IO
// for status push. Seek bar works in 100 ms units (see onStatus/seek).
(function () {
  var STATE = { state: "idle", src: null, volume: 1.0, position_s: 0,
                position_ms: 0, nodes: [], files: [], root: "",
                schedules: [], maxVolume: 10 };
  var $ = function (id) { return document.getElementById(id); };

  function api(path, body, method) {
    // Accept api(path, {method:"DELETE"}) shorthand used by the schedule list.
    if (!method && body && typeof body.method === "string" &&
        Object.keys(body).length === 1) {
      method = body.method;
      body = undefined;
    }
    var opts = { method: method || (body === undefined ? "GET" : "POST") };
    if (body !== undefined) {
      opts.headers = { "Content-Type": "application/json" };
      opts.body = JSON.stringify(body);
    }
    return fetch(path, opts).then(function (r) { return r.json(); });
  }

  // ---- library ----------------------------------------------------------
  function loadLibrary() {
    var root = STATE.root || $("libRoot").value.trim() || "";
    $("libInfo").textContent = "Scanning " + (root || "default folder") + " ...";
    api("/api/library?root=" + encodeURIComponent(root))
      .then(function (d) {
        STATE.root = d.root || root;
        STATE.files = d.files || [];
        $("libRoot").value = STATE.root;
        renderFiles();
        if (d.error) { showError(d.error); }
        if (STATE.files.length) {
          $("libInfo").textContent = STATE.files.length + " file(s) in " + STATE.root;
          if (!curPath()) { selectFile(0); }
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
      if (f.path === curPath()) { li.className = "sel"; }
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
    STATE.src_path = f.path;
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
  function curPath() { return STATE.src_path || STATE.src || null; }

  function doPlay() {
    if (!curPath()) {
      // Nothing selected yet: play the first library file if there is one,
      // otherwise ask for a library folder.
      if (STATE.files && STATE.files.length) { selectFile(0); }
      if (!curPath()) { pickFolder(); return; }
    }
    api("/api/play", { path: curPath(), volume: STATE.volume })
      .then(function (d) {
        if (d.error) { showError(d.error); }
      })
      .catch(function (e) { showError(e.message); });
  }

  function doStop() {
    api("/api/stop", {})
      .then(function () {
        $("playBtn").textContent = "Play";
        $("seekBar").value = 0;
        var f = STATE.files.find(function (x) { return x.path === curPath(); });
        $("posLabel").textContent = "0:00 / " + formatS((f && f.duration_s) || 0);
      })
      .catch(function (e) { showError(e.message); });
  }

  function doPause() {
    var paused = STATE.state === "paused";
    api(paused ? "/api/resume" : "/api/pause", {})
      .then(function (d) { if (d.error) { showError(d.error); } })
      .catch(function (e) { showError(e.message); });
  }

  function setVolume(v) {
    v = Math.min(STATE.maxVolume, Math.max(0, v));   // clamp to settings ceiling
    STATE.volume = v;
    api("/api/volume", { volume: v })
      .then(function (d) { if (d.error) { showError(d.error); } renderFooter(); })
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
    var pb = $("pauseBtn");
    pb.hidden = false;
    pb.disabled = !(STATE.state === "playing" || STATE.state === "paused");
    pb.textContent = STATE.state === "paused" ? "Resume" : "Pause";
    var f = STATE.files.find(function (x) { return x.path === curPath(); });
    var dur = (f && f.duration_s != null) ? f.duration_s : 0;
    $("seekBar").max = Math.max(1000, Math.round(dur * 10));   // 100 ms units
    // Server position is in ms; the slider counts 100 ms steps.
    if (document.activeElement !== $("seekBar")) {
      $("seekBar").value = Math.round((STATE.position_ms || 0) / 100);
    }
    $("posLabel").textContent =
      formatMs(STATE.position_ms) + " / " + formatS(dur);
    renderNodes();
    renderFooter();
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
      var rm = document.createElement("button");
      rm.type = "button"; rm.textContent = "Remove"; rm.className = "noderem";
      rm.addEventListener("click", function () {
        if (!confirm("Remove node " + n.ip + "?")) { return; }
        api("/api/nodes/remove", { ip: n.ip }).then(function (d) {
          if (d.error) { showError(d.error); return; }
          STATE.nodes = d.nodes; renderNodes(); renderFooter();
        }).catch(function (e) { showError(e.message); });
      });
      head.appendChild(nm);
      head.appendChild(ip);
      head.appendChild(rm);
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

  // ---- node discovery -----------------------------------------------------
  function discoverBoards() {
    $("discInfo").textContent = "Scanning network (a few seconds)…";
    $("discoverBtn").disabled = true;
    api("/api/nodes/discover", {}).then(function (d) {
      $("discoverBtn").disabled = false;
      if (d.error) { $("discInfo").textContent = ""; showError(d.error); return; }
      var cfgd = d.configured || [];
      var fresh = (d.found || []).filter(function (ip) {
        return cfgd.indexOf(ip) < 0;
      });
      $("discInfo").textContent = (d.found || []).length + " board(s) on " +
        d.subnet + (fresh.length ? " — " + fresh.length + " new" : " — all added");
      renderDiscovered(d.found || [], cfgd);
    }).catch(function (e) {
      $("discoverBtn").disabled = false;
      $("discInfo").textContent = "";
      showError("Discovery failed: " + e.message);
    });
  }

  function renderDiscovered(found, configured) {
    var ul = $("discList");
    if (!ul) { return; }
    ul.innerHTML = "";
    if (!found.length) {
      var li = document.createElement("li");
      li.className = "muted";
      li.textContent = "No Espressif boards found (is the board on the same WiFi?)";
      ul.appendChild(li);
      return;
    }
    found.forEach(function (ip) {
      var li = document.createElement("li");
      var lbl = document.createElement("span");
      lbl.className = "fname";
      lbl.textContent = ip;
      li.appendChild(lbl);
      if (configured.indexOf(ip) >= 0) {
        var tag = document.createElement("span");
        tag.className = "fdur";
        tag.textContent = "already added";
        li.appendChild(tag);
      } else {
        var add = document.createElement("button");
        add.type = "button"; add.textContent = "Add";
        add.addEventListener("click", function () {
          api("/api/nodes", { ip: ip }).then(function (d) {
            if (d.error) { showError(d.error); return; }
            STATE.nodes = d.nodes;
            discoverBoards();     // refresh tags
            renderFooter();
          }).catch(function (e) { showError(e.message); });
        });
        li.appendChild(add);
      }
      ul.appendChild(li);
    });
  }

  // ---- tabs / menus / footer / modals -------------------------------------
  // ---- scheduled play/stop ------------------------------------------------
  function renderSchedule(plans) {
    var ul = $("schedList");
    if (!ul) { return; }
    ul.innerHTML = "";
    if (!plans || !plans.length) {
      $("schedEmpty").hidden = false;
      return;
    }
    $("schedEmpty").hidden = true;
    plans.forEach(function (p) {
      var li = document.createElement("li");
      var name = document.createElement("span");
      name.className = "fname"; name.textContent = p.name;
      var time = document.createElement("span");
      time.className = "fdur"; time.textContent = p.time;
      var action = document.createElement("span");
      action.className = "fsz"; action.textContent = p.action;
      var rm = document.createElement("button");
      rm.type = "button"; rm.textContent = "Remove";
      rm.className = "noderem";
      rm.addEventListener("click", function () {
        api("/api/schedule/" + p.id, { method: "DELETE" })
          .then(function (d) {
            if (d.error) { showError(d.error); return; }
            STATE.schedules = d.plans || [];
            renderSchedule(STATE.schedules);
          }).catch(function (e) { showError(e.message); });
      });
      li.appendChild(name);
      li.appendChild(time);
      li.appendChild(action);
      li.appendChild(rm);
      ul.appendChild(li);
    });
  }

  function showAddSchedule() {
    var name = prompt("Plan name (e.g. 'Morning music')");
    if (!name || !name.trim()) { return; }
    var file = prompt("File name in the current library folder (e.g. song.mp3)");
    if (!file || !file.trim()) { return; }
    var time = prompt("Time to fire, HH:MM, e.g. 07:30");
    if (!time || !/^\d{2}:\d{2}$/.test(time)) {
      showError("Time must be HH:MM, e.g. 07:30"); return;
    }
    var action = confirm("Action: Play this file?") ? "play" : "stop";
    api("/api/schedule", { name: name.trim(), action: action,
                            file: file.trim(), time: time.trim() })
      .then(function (d) {
        if (d.error) { showError(d.error); return; }
        STATE.schedules = d.plans || [];
        renderSchedule(STATE.schedules);
        $("schedInfo").textContent = "Plan added at " + time.trim();
      }).catch(function (e) { showError("Schedule add failed: " + e.message); });
  }
  function showTab(name) {
    var panes = document.querySelectorAll(".tabpane");
    for (var i = 0; i < panes.length; i++) {
      panes[i].hidden = panes[i].id !== "tab-" + name;
    }
    var tabs = document.querySelectorAll(".tab");
    for (var j = 0; j < tabs.length; j++) {
      tabs[j].className = "tab" + (tabs[j].getAttribute("data-tab") === name ?
                                   " active" : "");
    }
  }

  function closeMenus() {
    var ms = document.querySelectorAll(".menu.open");
    for (var i = 0; i < ms.length; i++) { ms[i].classList.remove("open"); }
  }

  function menuAction(act) {
    if (act === "choose-lib") { pickFolder(); }
    else if (act === "rescan") { loadLibrary(); }
    else if (act === "play") { doPlay(); }
    else if (act === "stop") { doStop(); }
    else if (act === "goto-nodes") { showTab("nodes"); }
    else if (act === "discover") { showTab("nodes"); discoverBoards(); }
    else if (act === "help") { $("helpDlg").showModal(); }
    else if (act === "about") { $("aboutDlg").showModal(); }
  }

  function renderFooter() {
    $("stState").textContent = "state: " + STATE.state;
    $("stNodes").textContent = "nodes: " + STATE.nodes.length +
      (STATE.nodes.some(function (n) { return n.playing; }) ? " (streaming)" : "");
    $("stPos").textContent = "pos: " + formatMs(STATE.position_ms);
    $("stVol").textContent = "vol: " + Number(STATE.volume).toFixed(2);
    $("stServer").textContent = "server: " + (socket && socket.connected ?
                                              "connected" : "connecting…");
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
  // ---- equalizer ---------------------------------------------------------
  // VLC-style 10-band peaking EQ. Slider moves are debounced (each POST
  // restarts the ffmpeg pipeline when playing, so don't spam it).
  var EQ = { bands: [], min: -12, max: 12, presets: [] };
  var eqTimer = null, eqDrags = 0;

  function eqColumn(i, label) {
    var col = document.createElement("div");
    col.className = "eqcol" + (i < 0 ? " preamp" : "");
    var s = document.createElement("input");
    s.type = "range";
    s.min = EQ.min; s.max = EQ.max; s.step = 0.5; s.value = 0;
    s.id = i < 0 ? "eqPre" : "eqb" + i;
    s.setAttribute("aria-label", label);
    var db = document.createElement("span");
    db.className = "eqdb";
    db.id = i < 0 ? "eqPreDb" : "eqd" + i;
    db.textContent = "0.0 dB";
    var lb = document.createElement("span");
    lb.className = "eqband";
    lb.textContent = label;
    s.addEventListener("input", function () { eqSetLabel(i); eqSchedulePush(); });
    s.addEventListener("change", function () { eqSetLabel(i); eqPush(); });
    s.addEventListener("pointerdown", function () { eqDrags++; });
    s.addEventListener("pointerup", function () { eqDrags = Math.max(0, eqDrags - 1); });
    col.appendChild(s);
    col.appendChild(db);
    col.appendChild(lb);
    return col;
  }

  function bandLabel(hz) {
    return hz >= 1000 ? (hz / 1000) + " kHz" : hz + " Hz";
  }

  function eqSetLabel(i) {
    var el = i < 0 ? $("eqPre") : $("eqb" + i);
    var lab = i < 0 ? $("eqPreDb") : $("eqd" + i);
    var v = parseFloat(el.value);
    lab.textContent = (v > 0 ? "+" : "") + v.toFixed(1) + " dB";
  }

  function eqStateFromUi() {
    var gains = [];
    for (var i = 0; i < EQ.bands.length; i++) {
      gains.push(parseFloat($("eqb" + i).value));
    }
    return { enabled: $("eqEnable").checked,
             preamp_db: parseFloat($("eqPre").value),
             gains: gains };
  }

  function eqApplyState(eq) {
    if (!eq) { return; }
    $("eqEnable").checked = !!eq.enabled;
    $("eqPre").value = eq.preamp_db;
    eqSetLabel(-1);
    for (var i = 0; i < EQ.bands.length; i++) {
      $("eqb" + i).value = eq.gains[i];
      eqSetLabel(i);
    }
  }

  function eqSchedulePush() {
    clearTimeout(eqTimer);
    eqTimer = setTimeout(eqPush, 250);
  }

  function eqPush() {
    api("/api/eq", eqStateFromUi()).then(function (d) {
      if (d && d.error) { showError(d.error); }
    }).catch(function (e) { showError("EQ apply failed: " + e.message); });
  }

  function refreshPresets(names, selected) {
    var sel = $("eqPreset");
    sel.innerHTML = "<option value=''>Preset…</option>";
    names.forEach(function (p) {
      var o = document.createElement("option");
      o.value = p; o.textContent = p;
      sel.appendChild(o);
    });
    if (selected) { sel.value = selected; }
  }

  function buildEqUi() {
    api("/api/eq").then(function (d) {
      if (d && d.error) { showError(d.error); return; }
      EQ.bands = d.bands || [];
      EQ.min = d.min_db; EQ.max = d.max_db; EQ.presets = d.presets || [];
      var box = $("eqSliders");
      box.appendChild(eqColumn(-1, "Preamp"));
      EQ.bands.forEach(function (hz) {
        box.appendChild(eqColumn(EQ.bands.indexOf(hz), bandLabel(hz)));
      });
      refreshPresets(EQ.presets);
      eqApplyState(d);
    }).catch(function (e) { showError("EQ load failed: " + e.message); });
  }

  function onSavePreset() {
    var n = prompt("Save current EQ as preset (name):");
    if (!n || !n.trim()) { return; }
    api("/api/eq/presets", { name: n.trim() }).then(function (d) {
      if (d.error) { showError(d.error); return; }
      EQ.presets = d.presets || EQ.presets;
      refreshPresets(EQ.presets, n.trim());
    }).catch(function (e) { showError("Preset save failed: " + e.message); });
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
      if (d.src_path !== undefined) { STATE.src_path = d.src_path; }
      if (d.volume !== undefined) {
        STATE.volume = d.volume;
        $("volSlider").value = d.volume;
        $("volLabel").textContent = Number(d.volume).toFixed(2);
      }
      if (d.position_s !== undefined) { STATE.position_s = d.position_s; }
      if (d.position_ms !== undefined) { STATE.position_ms = d.position_ms; }
      if (d.nodes !== undefined) { STATE.nodes = d.nodes; }
      if (d.eq && eqDrags === 0) { eqApplyState(d.eq); }
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
      renderFooter();
    });
    socket.on("disconnect", function () {
      renderFooter();
    });
    socket.on("schedule_updated", function (d) {
      STATE.schedules = (d && d.plans) || [];
      renderSchedule(STATE.schedules);
    });
  }

  // ---- wiring -----------------------------------------------------------
  $("playBtn").addEventListener("click", doPlay);
  $("stopBtn").addEventListener("click", doStop);
  $("pauseBtn").addEventListener("click", doPause);
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
  $("eqEnable").addEventListener("change", eqPush);
  $("eqPreset").addEventListener("change", function () {
    var n = $("eqPreset").value;
    if (!n) { return; }
    api("/api/eq/preset", { name: n }).then(function (d) {
      if (d.error) { showError(d.error); return; }
      eqApplyState(d.eq);
    }).catch(function (e) { showError("Preset apply failed: " + e.message); });
  });
  $("eqSaveBtn").addEventListener("click", onSavePreset);

  // tabs, menus, nodes tab, modals
  var tabs = document.querySelectorAll(".tab");
  for (var t = 0; t < tabs.length; t++) {
    tabs[t].addEventListener("click", function () {
      showTab(this.getAttribute("data-tab"));
    });
  }
  var menus = document.querySelectorAll("[data-menu]");
  for (var m = 0; m < menus.length; m++) {
    (function (menu) {
      menu.querySelector(".menubtn").addEventListener("click", function (ev) {
        ev.stopPropagation();
        var was = menu.classList.contains("open");
        closeMenus();
        if (!was) { menu.classList.add("open"); }
      });
    })(menus[m]);
  }
  document.addEventListener("click", closeMenus);
  var acts = document.querySelectorAll(".dropdown [data-act]");
  for (var a = 0; a < acts.length; a++) {
    acts[a].addEventListener("click", function () {
      closeMenus();
      menuAction(this.getAttribute("data-act"));
    });
  }
  $("discoverBtn").addEventListener("click", discoverBoards);
  $("nodeAddBtn").addEventListener("click", function () {
    var ip = $("nodeIp").value.trim();
    if (!ip) { showError("Enter an IP address first"); return; }
    api("/api/nodes", { ip: ip }).then(function (d) {
      if (d.error) { showError(d.error); return; }
      STATE.nodes = d.nodes;
      $("nodeIp").value = "";
      renderNodes(); renderFooter();
    }).catch(function (e) { showError(e.message); });
  });
  var closeBtns = document.querySelectorAll(".closebtn");
  for (var c = 0; c < closeBtns.length; c++) {
    closeBtns[c].addEventListener("click", function () {
      this.closest("dialog").close();
    });
  }

  // ---- settings tab --------------------------------------------------------
  function settingsFill(s) {
    STATE.maxVolume = Math.max(0, Math.min(10, parseFloat(s.max_volume) || 1));
    $("setMaxVol").value = STATE.maxVolume;
    $("setDefEq").value = s.default_eq_preset || "";
    $("setLibRoot").value = s.default_library_root || "";
    $("volSlider").max = STATE.maxVolume;          // clamp the volume slider
    if (STATE.volume > STATE.maxVolume) {
      STATE.volume = STATE.maxVolume;
      $("volSlider").value = STATE.volume;
    }
  }

  function settingsLoadUi() {
    // Load the preset list first, then fill values — otherwise the saved
    // default-EQ name is set before its <option> exists and gets lost.
    Promise.all([
      api("/api/settings").catch(function () { return null; }),
      api("/api/eq").catch(function () { return null; })
    ]).then(function (res) {
      var d = res[0], e = res[1];
      var sel = $("setDefEq");
      var keep = sel.value;
      sel.innerHTML = '<option value="">(none — last used)</option>';
      ((e && e.presets) || []).forEach(function (p) {
        var o = document.createElement("option");
        o.value = p; o.textContent = p;
        sel.appendChild(o);
      });
      sel.value = keep;
      if (d && !d.error) { settingsFill(d.settings || {}); }
    });
  }


  $("setSaveBtn").addEventListener("click", function () {
    api("/api/settings", {
      max_volume: parseFloat($("setMaxVol").value) || 1,
      default_eq_preset: $("setDefEq").value || "",
      default_library_root: $("setLibRoot").value.trim() || ""
    }).then(function (d) {
      if (d.error) { showError(d.error); return; }
      settingsFill(d.settings || {});
      $("setInfo").textContent = "Saved ✓";
      setTimeout(function () { $("setInfo").textContent = ""; }, 4000);
      renderFooter();
    }).catch(function (e) { showError(e.message); });
  });

  // ---- schedule boot load ---------------------------------------------------
  function loadSchedules() {
    api("/api/schedule").then(function (d) {
      STATE.schedules = (d && d.plans) || [];
      renderSchedule(STATE.schedules);
    }).catch(function () { });
  }

  // ---- boot -------------------------------------------------------------
  $("libRoot").value = "";
  $("schedAddBtn").addEventListener("click", showAddSchedule);
  loadLibrary();
  buildEqUi();
  connectWS();
  settingsLoadUi();
  loadSchedules();
  // Apply the saved default EQ profile to the live EQ tab on boot.
  var bootDefaultPreset = null;
  api("/api/settings").then(function (d) {
    bootDefaultPreset = d && d.settings && d.settings.default_eq_preset;
    if (!bootDefaultPreset) { return; }
    return api("/api/eq/preset", { name: bootDefaultPreset });
  }).then(function () {
    return api("/api/eq");
  }).then(function (e) {
    if (e && e.eq) { eqApplyState(e.eq); }
    var sel = $("eqPreset");
    if (bootDefaultPreset && sel) {
      sel.value = bootDefaultPreset;      // show which profile is active
      if (sel.value !== bootDefaultPreset) { sel.value = ""; }
    }
  }).catch(function () { });
  // REST boot fill (footer/node list even before the first WS push).
  api("/api/status").then(function (d) {
    if (!d) { return; }
    STATE.state = d.state || "idle";
    STATE.src = d.src || null;
    STATE.src_path = d.src_path || null;
    STATE.volume = d.volume || 1.0;
    STATE.position_ms = d.position_ms || 0;
    STATE.nodes = d.nodes || [];
    $("volSlider").value = STATE.volume;
    $("volLabel").textContent = Number(STATE.volume).toFixed(2);
    if (STATE.src) { $("nowSrc").textContent = STATE.src; }
    renderNodes();
    renderFooter();
  }).catch(function () { /* server may still be starting */ });
  showTab("player");
})();
