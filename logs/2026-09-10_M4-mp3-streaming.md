# 2026-09-10 — MP3 file streaming + audio quality fixes (session 2)

## New feature: file mode in send_pcm.py (canonical file extended, no duplicates)
- `python send_pcm.py file <path> [port] [vol]` — decodes any audio file via
  ffmpeg (from `imageio-ffmpeg` pip package, static binary, no system ffmpeg) to
  48 kHz/16-bit/mono raw PCM and streams it in real time with pacing.
- First real content streamed: `D:\New folder\Pakistani_Songs_-_Untitled_(mp3.pm).mp3`
  (4.18MB, ~4.3 min) — end to end over TCP, played on speaker. ✅

## Problems found by user listening + fixes
1. **Volume too low** — root cause: SD pin driven to VDD = MAX98357A *minimum* gain (3dB).
   Fix: digital gain PCM_GAIN in pump (`main.c`) + sender decodes at -7dB headroom
   (`volume=0.45`). x4 attempt = heavy clipping distortion (user: "still bad") → final **x2 (+6dB)**.
2. **Jerky when monitor attached** — root cause: pump only wrote 5.3ms audio/loop then
   slept 4ms (barely real-time); USB CDC printf flooding from tcp_task starved it.
   Fix: pump now writes 21.3ms chunks (1024 frames), tcp progress logs throttled to
   1 per 5s, 170ms playback prefill before play starts (ring >= 16384 bytes).

## Result after x2+headroom fix
- User: "better but still some jerks" — suspects **shared power rail sag** (amp 3W peaks
  on USB 5V shared with board+WiFi). NEXT: user tests amp on separate 5V supply
  (common GND). If jerks persist → increase jitter prefill.

## Infrastructure notes
- Start-Process with paths containing spaces: quote args with backtick-quote `"
- Monitor log via pwsh pipe to Out-File is block-buffered — board logs only visible
  after monitor exits; don't misread stale tails mid-run.


## RGB LED feature (2026-09-10, later)
- Single onboard WS2812 RGB on GPIO48 (led_strip 3.0.3 via idf_component.yml) does everything:
  - wifi down = solid dim red; waiting = blue breathing; streaming = VU (green quiet -> red loud), peak-driven fast attack / slow decay
- net_state updated in wifi_event_handler + tcp_task; vu_level computed in pump (peak/128, decay 8/chunk)
- Verified by user: connection colors + VU working
- User-confirmed: power-on tone limited to ~2s then silence; pump pacing regression (14ms) fixed back to 4ms = no more periodic long tones
