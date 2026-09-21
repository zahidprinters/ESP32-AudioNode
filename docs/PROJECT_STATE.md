# Project State

ESP32 AudioNode is an ESP32-S3 WiFi speaker box. A board joins your WiFi, then plays PCM audio streamed to it over RTP/UDP by a PC server on the same network.

## What this is

An ESP32-S3 board with a MAX98357A class-D amplifier and a WS2812 RGB LED, flashed with firmware that joins a WiFi network from saved credentials and listens for RTP L16 audio on UDP port 1234. A PC server on the same network streams audio to the board; the board plays it through an attached speaker.

## Repository layout

- irmware/ — ESP32-S3 firmware (idf.py build from here; flash with idf.py -p COM5 flash).
- udio_player/ — the PC-side server: a browser app (Flask + Socket.IO), a CLI sender, an equalizer, and a selftest.
- docs/ — all project documentation.
- .cline/ — agent tooling and next-version planning (not part of the shipped product).
- logs/ — local session logs (git-ignored).

## Build and run

- Firmware: ESP-IDF v6.1 at D:\esp32\v6.1\esp-idf. Set up the environment with 	ools\env.ps1, then from irmware/ run idf.py set-target esp32s3, idf.py build, and idf.py -p COM5 flash.
- PC app: Python 3.8+ with 
umpy, imageio-ffmpeg (ffmpeg), and on Windows pyaudiowpatch for loopback mode. Run from the repository root: python -m audio_player.app starts the browser UI at http://localhost:5000.

## What has been verified

- WiFi: the board joins from saved credentials, gets an IP, and listens on UDP port 1234.
- Setup: a first boot, factory reset, or WiFi failover opens an AudioNode-Setup access point at 192.168.4.1. The captive portal saves WiFi SSID and password, server IP, server port, and node name to non-volatile storage. Saving reboots the board to station mode.
- Factory reset: holding the BOOT button for about 5 seconds erases the saved configuration and reboots the board to the setup access point.
- Audio: RTP L16 over UDP at 48 kHz, 16-bit, mono, 20 ms frames. The board validates each packet and fills gaps with silence; it never blocks audio output waiting for a missing packet. A 20-second stream showed 821 packets received with zero drops, byte-exact with the sent frame count.
- LED: the RGB LED indicates state — red when WiFi is down, blue breathing while waiting for audio, and a green-to-yellow-to-red VU meter while streaming.
- App: the browser app's equalizer, play/stop/seek/volume, and position tracking were checked by a 29-check self-test that validates the RTP wire format, frame math, real-time pacing, position across restarts, and the UI element contract.

## Version notes

This release extends the setup portal with two new fields:

- **Node name**: an optional label for the board, saved with the WiFi credentials and server address.
- **Server port**: the UDP port the board listens on. The default is 1234; the field is preserved when left blank. This is wired into the UDP listener, so the port the board actually binds to matches what is saved.

The configuration blob carries a version, so a board flashed with this firmware rejects its old configuration once and returns to the setup access point for one re-provision.

A /debug route is available on the setup access point at http://192.168.4.1/debug. It returns a JSON snapshot of the board's current configuration and state — version, WiFi SSID, server IP, whether a server IP is saved, server port, node name, network state, playback state, ring buffer usage, and whether the access point is active. This is useful for confirming a portal save without a serial connection.

## Known limits

- The board's pins are fixed: I2S on GPIO 4 (BCLK), 5 (LRC), and 6 (DIN), amplifier enable on GPIO 15, RGB LED on GPIO 48, and BOOT button on GPIO 0. They are not configurable from the portal.
- The PC app currently sends to one board at a time from the browser UI, or one board per CLI sender instance. Sending the same stream to multiple boards is supported by listing several nodes; multicast is a future enhancement.
- Compressed streaming (MP3, AAC) over HTTP or RTP is a future board-side path; the current product uses raw RTP L16.
- A packaged Windows installer for the PC app is not part of this release.