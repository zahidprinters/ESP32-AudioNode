# Product Context

## The problem

Setting up a networked speaker normally means an app, an account, and a cloud
service that has to keep working forever. This project removes all three. The
board is provisioned by any browser on the network, stores its own config, and
streams from a server the owner already controls.

## Who it is for

A person who wants a bare ESP32-S3 board to behave as a network speaker, and
who would rather own the server than subscribe to anything.

## What it does
- **Board** — ESP32-S3 + MAX98357A. Joins Wi-Fi from NVS-stored credentials,
  then waits for audio. On-board WS2812 LED shows state: red = no Wi-Fi, blue
  breathing = waiting, VU meter = streaming.
- **Provisioning** — on first boot, or after holding BOOT for 5 s, the board
  raises the open AP `AudioNode-Setup`. A page at `http://192.168.4.1` captures
  Wi-Fi, server address, port and node name into NVS, then reboots into STA.
- **Server** — Flask + Socket.IO: browse a music folder, play/stop/seek,
  volume, 10-band EQ with saved presets, node management, LAN discovery,
  scheduled play/stop. One stream fans out to several boards.
- **Wire format** — RTP L16 over UDP, 48 kHz / 16-bit / mono / 20 ms frames,
  payload type 96, sequence +1 and timestamp +960 per frame.

## User experience goals
- Provisioning a new board should be a two-minute job with no app.
- The LED must always answer "what is the board doing right now" without logs.
- The web app should feel like a music player, not an admin console.

## What we are deliberately not doing
- **Clock-synchronised multi-board playback.** Fan-out works; the boards are
  *not* sample-aligned. This is a known limitation, stated plainly rather than
  hidden behind a "multi-node" claim.
- Packaging and an end-user installer. Not started.
