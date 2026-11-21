# Running several streams, several AI agents and several channels

The clipper makes clips. The [GTA Auto Sender](https://github.com/AnIntellectualBeing/GTA-Auto-Sender) posts them to
as many YouTube + Instagram channels as you connect and shares the clips equally. This page shows how to run
many streams and many AI sessions at the same time without them stepping on each other.

```
stream 1 -> clip.py -+
stream 2 -> clip.py -+-> output\  -> checker AI vetoes bad clips (output\<clip>.bad)
stream 3 -> clip.py -+        |
                              v
                       Sender: clip_feeder.py -> queue\<channel>\ready -> autopost.py -> Zernio -> YouTube + Instagram
```

## Roles (one AI can do all of them, or split them across sessions)

| Role | Does | Must not |
|---|---|---|
| **Capture runner** (1-3 sessions) | finds a live GTA stream nobody else uses, looks at one real frame, starts `run-live.ps1` for it, restarts it if it dies | start a stream another runner already has; pass `--gameplay-confirmed` without looking |
| **Checker** (1 session) | looks at frames from 3 s, 10 s, 20 s of every new clip within 10 minutes and writes `output\<clip>.bad` (one line why) for bad ones | edit code or the queue by hand |
| **Editor** (exactly 1 session) | the only one allowed to change scripts or config | share that job with anyone else |

Nobody uploads or calls `publish.py` by hand for clips the Sender handles: that double-posts.

## One capture per stream

```powershell
Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','<sender>\scripts\run-live.ps1','-Url','STREAM_URL','-Name','creator1','-Clipper','<clipper folder>' -WindowStyle Minimized
```

Pick a stream nobody else uses: `Get-ChildItem work\live-*.runs.log | ? LastWriteTime -gt (Get-Date).AddMinutes(-10)`
lists the streams already being captured. Each capture records and renders, so it needs RAM: if the PC slows down or
captures die, run fewer. Logs: `work\live-NAME.runs.log`, `work\live-NAME-<n>.log`.

## Checker veto: look at frames, then decide

Veto a clip (create `output\<clip>.bad` with one line why) if: the character or car is at the edge of the frame,
a streamer webcam shows, it is a menu / map / loading screen, captions are missing, stacked or garbled, the creator
credit is missing, or it is not safe for YouTube. The Sender never posts a vetoed clip and pulls it back out of
`ready\` if it has not gone yet. If three clips in a row from one stream are vetoed for the same reason, stop that
stream and pick another.

## Limits that decide how many channels you need

* YouTube refuses uploads past about **10 per channel per 24 hours** on a normal channel ("The user has exceeded the
  number of videos they may upload"). The Sender caps YouTube per channel (`youtube_per_day`, default 10) and sends
  surplus clips to Instagram only. Verifying each channel with a phone number raises YouTube's limit.
* Instagram's API allows about **50 posts per 24 hours** per account (`instagram_per_day`, default 45).
* Each clip goes to exactly one channel, never the same clip to two channels. More channels = more posts per day.
* Hundreds of near-identical uploads in a night can be flagged as repetitive: start low and raise the pace slowly.

## Captions and language

English speech stays English. Hindi becomes romanized Hinglish, and once a stream is clearly Hindi the clipper locks
onto Hindi for the rest of the stream (force it with `--spoken-language hi`). Any other language gets no captions.

## Only clip what you may use

Use a stream only when its creator allows clipping or you hold the rights. Keep the creator credit. If the rights are
unclear, ask the creator or skip the stream.
