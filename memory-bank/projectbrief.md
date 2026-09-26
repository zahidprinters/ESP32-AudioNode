# Project Brief

## What this is

**ESP32 AudioNode** — a Wi-Fi speaker you provision from a browser. An ESP32-S3
with a MAX98357A I2S amplifier joins your network from credentials it stores
itself, then plays 48 kHz mono audio streamed to it by a Python server on the
same LAN, as RTP L16 over UDP.

## Hard requirements
- Single-board streaming must be **verified on hardware**, not inferred.
- Board provisioning happens over an open access point at `192.168.4.1`, with no
  phone app and no cloud account.
- Audio format is fixed: 48 kHz, 16-bit, mono, 20 ms frames (960 samples =
  1920 bytes), payload type 96.
- "Connected" / "playing" in the UI must never be presented as proof the
  speaker is producing sound — the board has no back-channel to report that.

## Explicitly out of scope
- Cloud accounts, remote hosting, internet streaming.
- Native mobile apps.
- Lossless or compressed audio (the wire format is raw PCM by design).

## Success criteria
- 1 kHz tone reaches the speaker, confirmed by microphone recording
  (tone/noise ratio ~99x, already measured).
- Zero dropped packets over a sustained stream, byte-exact against send count.
- A board with empty NVS comes up on the setup AP and, once configured, joins
  Wi-Fi and receives audio without further intervention.
