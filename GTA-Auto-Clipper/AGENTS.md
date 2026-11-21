# Instructions for AI agents

Use this repository's commands as documented in [README.md](README.md). Keep all API keys in the local environment; never print, ask the user to paste, or write keys into prompts, logs, metadata, or tracked files.

## Clip workflow

1. Run `python find_streams.py "GTA 6" --max 25 --json` and show the returned candidates. The ranking is YouTube's view-count search order, not current concurrent viewers.
2. Use a stream only when the user has authorized its use or has a standing source list that includes it. If rights are unclear, ask the user and do not capture it.
3. Run `python clip.py URL --max-seconds 0 --clip-len 30 --lead-in 6 --top 2`. Stop after the requested review period or when the user stops the run.
4. Inspect each MP4 and its JSON. Confirm the highlight includes its lead-in and payoff, gameplay is centered, captions are legible and in sync, the audio is intelligible, and metadata is accurate.
5. Draft truthful titles, descriptions, captions, and hashtags from the clip. Do not invent reactions, events, creator approval, or viewership data.
6. Run `zernio_publish.py` without `--publish` to preview. Publish only when the user authorized this specific clip or previously enabled unattended publishing for authorized sources. For unattended use, require `GTA_UNATTENDED_POSTS=1`, both account IDs, and `--unattended`.
7. After posting, report the Zernio post ID and status. If a request errors after upload, check Zernio before retrying.

The clipper itself never posts. A `--test` output is not publishable. The source allowlist was intentionally removed; the agent must still respect the user's rights policy.
