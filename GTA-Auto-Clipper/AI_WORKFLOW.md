# AI workflow

This is the short public runbook. The paid guide adds setup screenshots, reusable prompts, channel/account setup, and a recurring unattended workflow.

```text
1. Use a user-provided video or live link when available. Otherwise search: `python find_streams.py "GTA 6 gameplay" --max 25 --json`, evaluate the full result set, and automatically select every source within the user's standing source-rights policy. Ask once to define that policy if none exists; do not ask the user to select streams individually.
2. Open and inspect each selected candidate's actual video. Confirm gameplay is visible on screen; a title, thumbnail, commentary, or facecam is not enough. If the AI cannot visually inspect a source, ask for a screenshot or use a user-provided video. Also confirm every source is one the user is allowed to record and share.
3. Capture only after that visual check: `python clip.py STREAM_URL --gameplay-confirmed --max-seconds 0 --clip-len 30 --lead-in 6 --top 2`.
4. By default the clipper ranks moments by live-chat reactions. If chat cannot connect or a chunk has no chat messages, it falls back to audio and speech. Choose `--moment-source combined` to use all signals together, or `--moment-source audio` for audio and speech only. YouTube chat uses `YOUTUBE_API_KEY`; Twitch chat needs private Twitch credentials.
5. Inspect every `output/*.mp4` and matching `output/*.json`; confirm gameplay is visible and gameplay fills the whole 9:16 screen, and captions are short one-line phrases at one fixed spot where each word pops in yellow when spoken. English speech stays English; Hindi speech is romanized Hinglish; other or uncertain speech has no captions. The source audio stays unchanged.
6. Preview with `python zernio_publish.py output/CLIP_ID --scheduled-for YYYY-MM-DDTHH:MM:SS+05:30`.
7. For ordinary publishing, add `--publish` only for a clip the user approved. For unattended scheduled posting without per-clip approval, require the one-time account/Zernio setup, `GTA_UNATTENDED_POSTS=1`, `--unattended`, a future schedule, and the user's standing source-rights policy. Never publish test clips or use `--now` in unattended mode.
```

For sleep-time scheduling, set the Zernio API key and account IDs outside the prompt. A scheduled post can go live while the computer sleeps; discovering streams and rendering clips cannot.

For a no-plugin, copy-and-paste assistant prompt, see [GTA-CLIPPING-PROMPT.txt](GTA-CLIPPING-PROMPT.txt). Pasting the prompt requires no special AI setup; creating clips automatically still requires access to this project and its local dependencies.

## Standing unattended mode

After one-time setup, a user can set `GTA_UNATTENDED_POSTS=1` in the private environment and grant the agent a standing source-rights policy. The agent must use only authorized creators, use `--unattended`, set a future `--scheduled-for` time, and review Zernio's returned status. It must not use `--now` for unattended runs.
