# GTA Auto Sender

The posting half of the [GTA Auto Clipper](https://github.com/AnIntellectualBeing/GTA-Auto-Clipper).
The clipper makes 9:16 clips. This kit takes those clips and posts them to **several YouTube + Instagram
channels at once**, sharing the clips equally, with no per-clip work from you.

```
live streams ──> clip.py (one per stream) ──> clipper output\ ──> clip_feeder.py ──> queue\<channel>\ready ──> autopost.py ──> Zernio ──> YouTube + Instagram
                                                    ^                                                      (every 5 min)
                                  a checker AI vetoes bad clips with output\<clip>.bad
```

* `clip_feeder.py` gives each clip (best score first) to the channel that has been fed the fewest clips, on that
  channel's next free slot. Tests, non-gameplay and vetoed clips are never fed.
* `autopost.py` uploads what is in `ready\`, schedules it for its exact time, retries only the platform that failed
  (no double posts), and writes `queue\RUNWAY.md` (how many days of posts each channel has left).
* `scripts\install-tasks.ps1` runs both every 5 minutes, hidden. `scripts\run-live.ps1` keeps one capture alive per stream.
* Video format is **9:16 only**. The clipper's default `--layout fill` fills the screen with the gameplay;
  `--layout fit` is an option that shows the whole source small over a blurred background (still 9:16).

## Set up (about 10 minutes)

1. Install Python 3.10+ and the [GTA Auto Clipper](https://github.com/AnIntellectualBeing/GTA-Auto-Clipper).
2. In [Zernio](https://zernio.com): create a profile, connect each YouTube channel and Instagram account
   (Instagram must be Creator or Business), then Settings > API Keys > create a key.
3. `copy .env.example .env` and put the key after `ZERNIO_KEY_MAIN=`. The name on the left must match `key_env` in `config\channels.json` (it is `ZERNIO_KEY_MAIN` in the example); use a new name per Zernio account if you have several keys. `copy config\channels.example.json config\channels.json`
   and fill in: your Zernio account IDs per channel, `clipper_output` (the clipper's `output` folder), the time
   zone offset, and the posts per hour. One Zernio key can serve many channels. Both files are git-ignored.
4. Test with nothing posted: `python -m unittest discover -s tests -p "test_*.py"` then `python clip_feeder.py --dry`
   and `python autopost.py --dry`.
5. `powershell -ExecutionPolicy Bypass -File scripts\install-tasks.ps1`.
6. Start a capture per live GTA stream: `scripts\run-live.ps1` (see its header). Look at a real frame first.

`PROMPT.txt` is the master prompt to paste into your AI agent (it installs this kit and the clipper for you).

## Rules that save you

* **YouTube's daily limit.** A normal YouTube channel refuses uploads past about 10 per 24 hours ("exceeded the number of videos they may upload"); those posts fail and the clip is lost. `youtube_per_day` (default 10) caps YouTube per channel and the feeder sends the surplus to Instagram only (`instagram_per_day`, default 45). Phone-verify each YouTube channel to raise the limit. More channels = more posts a day.
* **Posting pace.** Start with 3-6 YouTube posts an hour per channel and raise it slowly. Hundreds of near-identical
  uploads in one night can be flagged as repetitive. Instagram's API caps about 50 posts per 24 hours per account:
  `instagram_per_hour` puts the best slots there, everything else goes to YouTube only.
* **Veto, don't delete.** A checker agent looks at frames from each new clip and creates `output\<clip>.bad` (one line why).
  The feeder never posts it and pulls it back out of `ready\` if it has not gone yet.
* **One agent edits code.** Many AI sessions can run captures and check clips at the same time, but only one should
  change scripts or the config.
* **Files without BOM.** Write JSON as UTF-8 without a byte-order mark. These scripts tolerate it, other tools may not.
* **Keys stay private.** Only in `.env`. Never in chat, logs, clip files or git.
* **Keep the PC awake and online** to capture and feed. Posts already accepted by Zernio go out on time even if it sleeps.
* **Several streams need RAM.** Each capture records and renders; if the PC slows or captures die, run fewer.

You are responsible for what you post. Independent fan-made software, not affiliated with Rockstar Games,
Take-Two Interactive, YouTube, Instagram or Meta.
