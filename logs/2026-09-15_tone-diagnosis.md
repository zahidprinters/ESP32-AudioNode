# 2026-09-15 — Tone-by-tone distortion diagnosis (user ear test)

## Trigger
User asked: "maybe amp and speaker mismatch??" after bass distortion on songs.
User requested: analyze the MP3, play single tones one at a time, report which distort.

## Song analysis (tmp/spec_scan.py — 90 s of Pakistani_Songs_-_Untitled_(mp3.pm).mp3)
Octave bands (dB rel loudest): 31 Hz 0.0 | 63 Hz −1.3 | 125 Hz −1.9 | 250 −7.3 |
500 −3.4 | 1k −2.2 | 2k −3.7 | 4k −8.1 | 8k −11.4
Top peaks: **41 Hz**, 123 Hz, 691, 779, 416, 1394, 310, 937, 205, 1043 Hz.
→ Song is dominated by 31–63 Hz SUB-BASS (peak at 41 Hz). A small 3 W driver
cannot reproduce this without cone over-excursion → prime suspect for the
"damaged speaker" sound.

## Board gain chain (verified in firmware/main/main.c)
- Line 103: `#define PCM_GAIN 2` — board multiplies every sample ×2.
- Lines 105–108: `gain_clip()` saturates at ±32767 (flat-top clipping, no wrap).
- Consequence: sender level >0.5 (peak >16383) clips at the board.
  Vol 0.8 → 25600 ×2 = 51200 → clamped. **App default_volume=1.0 clips every peak.**
- Max CLEAN chain level: sender 0.5 → ×2 → full-scale DAC.

## Test ladder (8 tones, 4 s each, 1.3 s gap, via audio_player/send_pcm.py tone)
1=41 Hz, 2=63 Hz, 3=123 Hz, 4=250 Hz, 5=500 Hz, 6=1 kHz, 7=2 kHz, 8=4 kHz
- Round 1: vol 0.5 (max clean) → identifies speaker physical limits.
- Round 2: vol 0.8 (clips digitally) → separates digital clip from speaker buzz.

## Interpretation matrix
- Distorts in BOTH rounds → speaker/amp physical limit (excursion on bass,
  or undersized/worn driver if mids also buzz).
- Distorts ONLY in round 2 → digital clipping at board's ×2 (sender-side limit).
- Clean everywhere → distortion is song-content specific → next: play song slices.

## Results
- Round 1 (vol 0.5, clean level): **tones 4 (250 Hz), 5 (500 Hz), 6 (1 kHz) distort —
  the mids. Bass tones 1–3 (41/63/123 Hz) CLEAN.**
- Round 2 (vol 0.8): same pattern; all other tones just edgier (digital clip, expected).
- Round 3 (vol 0.3, quiet, mids only): user report — mids still most prominent,
  but user verdict: **"speaker is OK"** — mids simply work hardest on this driver,
  highs (2k/4k) sound cleanest. Accepted as speaker character, not a fault.

## Action taken: chain re-tuned to measurements (player.py + config.py)
Old chain: volume + lowshelf -6 dB @ 150 Hz. New chain (in this order):
```
highpass=f=65,lowshelf=f=120:g=-3,
acompressor=threshold=-18dB:ratio=3:attack=10:release=150,
volume={vol},alimiter=limit=0.5:level=disabled
```
Why, mapped to evidence:
- **highpass 65 Hz** — song's dominant peak is 41 Hz; driver can't reproduce it,
  it only eats headroom and causes mid intermodulation (mids = distortion zone).
- **bass shelf softened -6@150 → -3@120** — bass tones measured CLEAN in the ladder;
  the old shelf over-corrected and thinned the song's 125 Hz bass note.
- **acompressor -18 dB 3:1** — density/loudness without harder peaks.
- **alimiter 0.5 FS, LAST** — board x2 gain saturates above sender 0.5 FS
  (main.c gain_clip clamps at 32767). Ceiling guarantees the DAC never clips
  at ANY volume; app default_volume=1.0 is now safe (was guaranteed-clip before).

## Verification
- selftest: all checks passed.
- ffmpeg smoke test of the generated chain on the real song: exit 0, 18.2x speed.
- Server restarted, POST /api/play → state=playing, pos advancing (vol=1.0),
  log confirms full tuned chain in ffmpeg argv. [user ear verdict pending]


