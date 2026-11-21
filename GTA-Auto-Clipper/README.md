# GTA Auto Clipper

Find high-energy moments in live gameplay and render full-screen 9:16 clips with pop-up captions: each word pops in yellow the moment it is spoken. The clipper runs on your computer. A separate Zernio command can schedule the finished clip to your connected YouTube and Instagram accounts.

The software is free and MIT-licensed. The optional AI workflow guide and prompt pack are a separate digital product.

## What it does

- Searches current YouTube live results for a phrase such as `GTA 6` and prints machine-readable JSON for AI agents.
- Requires an explicit visual confirmation before live capture, so a discussion stream or facecam-only source is not silently treated as gameplay.
- Records a live source in rolling chunks. By default it ranks moments by live-chat reactions, then falls back to audio and speech if chat is unavailable or has no messages for a chunk. Combined chat, audio, and speech scoring is also available.
- Starts clips a few seconds before the detected highlight (6 seconds by default).
- Captions English speech in English and Hindi speech in romanized Hinglish. Other or uncertain languages, including Hindi the recognizer returns in an unsupported script, have no captions. Captions are short one-line phrases (up to 3 words) at one fixed spot: each word pops in yellow when it is spoken, earlier words turn white, and the next phrase replaces the last one in the same place (never stacked). Source audio stays unchanged.
- Places captions in the lower third of the visible gameplay panel instead of using one fixed position near the bottom of the full vertical canvas.
- Fills the whole 9:16 screen with gameplay by default (`--layout fill`), centered on the player. It samples frames for facecams, shifts the crop away from a persistent side facecam, and in stacked portrait streams cuts out the facecam and fills the screen with the gameplay part. `--layout fit` keeps the old look: the full source in the middle over a blurred background.
- Resets audio and video timestamps before burning the captions.
- Masks swear words and sexual words in the burned-in captions (for example `s***`) so platforms do not limit the clip; the original audio is unchanged.
- Saves MP4 and JSON metadata in `output/`. It never posts as part of clipping.
- Schedules reviewed clips through Zernio by default. Optional unattended scheduling is available after account setup and with a standing source-rights policy; dry-run is the default.

## Install

Requirements: Python 3.10+, FFmpeg in PATH, Node.js or Deno (yt-dlp needs a JavaScript runtime to read YouTube; the clipper uses Node automatically when Deno is missing), OpenCV for `--crop` face detection, and a stable connection for first-run speech-model downloads.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

For live-stream search and optional YouTube live-chat scoring, set a YouTube Data API key in the terminal. Keep keys out of prompts, source files, and GitHub:

```powershell
$env:YOUTUBE_API_KEY = "YOUR_YOUTUBE_DATA_API_KEY"
python find_streams.py "GTA 6" --max 25 --json
```

The YouTube API returns live search candidates in `viewCount` order. It is not a dependable ranking of current live viewers; open a candidate and confirm the stream before use.

## Make clips

Open the candidate stream and verify that actual GTA gameplay is visible in the video. A GTA title, thumbnail, or talking head is not enough. Then start capture and keep it running until you press Ctrl+C. The default is chat-first. If chat is unavailable or has no messages for a chunk, the clipper automatically uses audio and speech instead. The clipper writes each selected highlight to `output/`:

```powershell
python clip.py "https://www.youtube.com/watch?v=VIDEO_ID" --gameplay-confirmed --max-seconds 0 --clip-len 30 --lead-in 6 --top 2
```

Important options:

| Option | Default | Purpose |
| --- | ---: | --- |
| `--max-seconds` | `0` | Capture duration; `0` runs until stopped |
| `--chunk` | `90` | Analysis chunk size in seconds |
| `--clip-len` | `30` | Rendered highlight length |
| `--lead-in` | `6` | Seconds before the detected moment |
| `--top` | `1` | Highlights kept from each chunk |
| `--gameplay-confirmed` | required for live capture | Confirm you inspected the stream and saw actual gameplay before recording |
| `--min-score` | `2.5` | Minimum moment score |
| `--layout` | `fill` | `fill`: gameplay covers the full 9:16 screen, facecams cropped out. `fit`: full source in the middle over a blurred background |
| `--crop` | off | Old flag, same as `--layout fill` |
| `--moment-source` | `chat` | Choose `chat`, `combined`, or `audio` for highlight selection |
| `--spoken-language` | `auto` | `auto` detects the language and locks to Hindi (Hinglish captions) once a stream is clearly Hindi. `hi` / `en` force it for the whole stream |
| `--no-chat` | off | Skip live-chat collection and use audio and speech only |
| `--output-dir` | `output/` | Custom destination folder |

Examples: `--moment-source chat` uses chat reactions first; `--moment-source combined` scores chat, audio, and speech together; `--moment-source audio` uses the original audio and speech method. Chat mode falls back to audio and speech when it has no chat data.

Test a local video first. Test output goes to `test_out/` and cannot be published:

```powershell
python clip.py --file "C:\videos\gameplay.mp4" --test --clip-len 30
```

## Schedule to YouTube + Instagram

Connect your YouTube account and an Instagram Creator or Business account to Zernio. Set the key and account IDs as private environment variables:

```powershell
$env:ZERNIO_API_KEY = "YOUR_ZERNIO_API_KEY"
$env:ZERNIO_YOUTUBE_ACCOUNT_ID = "YOUR_YOUTUBE_ACCOUNT_ID"
$env:ZERNIO_INSTAGRAM_ACCOUNT_ID = "YOUR_INSTAGRAM_ACCOUNT_ID"
```

Review the clip and its JSON metadata, then mark the metadata `"approved": true`. Preview the schedule first:

```powershell
python zernio_publish.py "output\gta-CLIP-ID" --scheduled-for "2026-11-18T12:00:00+05:30"
```

The dry run sends nothing. To schedule the post to both accounts, add `--publish`:

```powershell
python zernio_publish.py "output\gta-CLIP-ID" --scheduled-for "2026-11-18T12:00:00+05:30" --publish
```

For unattended posting, first make sure the AI agent is restricted to sources you have the right to use and that you have tested its output. Then set `GTA_UNATTENDED_POSTS=1` in the machine's private environment and run with `--publish --unattended`. A scheduled post already accepted by Zernio can publish while your computer is asleep. Discovery and clip rendering still require an awake, connected runner.

`publish.py` is the same command as `zernio_publish.py`, but it also accepts the generic variable names `PUBLISH_API_KEY`, `PUBLISH_YOUTUBE_ACCOUNT_ID` and `PUBLISH_INSTAGRAM_ACCOUNT_ID`, so either spelling works: `python publish.py "output\gta-CLIP-ID" --publish --unattended --scheduled-for "FUTURE_ISO_TIME"`. To post to many channels with an equal share, use [GTA Auto Sender](https://github.com/AnIntellectualBeing/GTA-Auto-Sender).

The publisher stores the Zernio post ID and an idempotency key in the metadata. If an API call fails, check the Zernio dashboard before retrying.

## Use with any AI assistant

Copy [GTA-CLIPPING-PROMPT.txt](GTA-CLIPPING-PROMPT.txt) into ChatGPT, Claude, Gemini, or another AI assistant. The prompt itself needs no API key, plugin, or special setup. If your AI can access your video and run local tools, it can help operate the clipper; otherwise it will tell you what it can do and guide you one step at a time. Automatic clipping still needs the free tool installed. YouTube chat scoring uses the same optional YouTube API key as live search; without it, audio and speech scoring still works.

For an AI that can access this project folder, [AI_WORKFLOW.md](AI_WORKFLOW.md) gives the detailed tool workflow. Never paste credentials into a prompt.

## Rights and platform notes

This release has no creator allowlist; the user chooses the source. You are responsible for obtaining rights and permissions to record, edit, and publish the footage. Creator credit does not replace permission. YouTube search ranking does not report a verified live concurrent-viewer leaderboard. This independent fan project is not affiliated with Rockstar Games, Take-Two Interactive, YouTube, Instagram, Meta, or Zernio.

## License

MIT. See [LICENSE](LICENSE). No OpenShorts application code or AutoCrop-Vertical code is bundled in this focused release.

## Several streams, several AI agents, several channels

See [docs/MULTI-AGENT.md](docs/MULTI-AGENT.md) for the roles (capture runner, checker, editor), running one capture per stream, the checker's veto rules, and the YouTube/Instagram daily limits. Posting to many channels with an equal share: [GTA Auto Sender](https://github.com/AnIntellectualBeing/GTA-Auto-Sender).
