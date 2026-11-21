# GTA Gameplay Clipping & Social Publishing Automation System
## Complete Setup, Configuration, Testing, and Operations Guide (Windows)

This document provides complete, step-by-step, copy-pasteable PowerShell instructions for deploying, configuring, testing, and operating the integrated **GTA-Auto-Clipper** and **GTA-Auto-Sender** pipeline on Windows 10/11.

---

## Table of Contents
1. [System Architecture & Code Layout](#system-architecture--code-layout)
2. [Verified Environment & Tool Versions](#verified-environment--tool-versions)
3. [Section 1: Prerequisites Installation](#section-1-prerequisites-installation)
4. [Section 2: Repositories Setup & Directory Structure](#section-2-repositories-setup--directory-structure)
5. [Section 3: Shared Python Virtual Environment (.venv) Setup](#section-3-shared-python-virtual-environment-venv-setup)
6. [Section 4: GTA-Auto-Clipper Configuration & Local Testing](#section-4-gta-auto-clipper-configuration--local-testing)
7. [Section 5: GTA-Auto-Sender Configuration & Credential Security](#section-5-gta-auto-sender-configuration--credential-security)
8. [Section 6: Unit Test Suite Execution](#section-6-unit-test-suite-execution)
9. [Section 7: Dry-Run Verification & Filter Safety Matrix](#section-7-dry-run-verification--filter-safety-matrix)
10. [Section 8: Windows Task Scheduler Automation](#section-8-windows-task-scheduler-automation)
11. [Section 9: Troubleshooting Guide](#section-9-troubleshooting-guide)
12. [Section 10: Manual Next Steps for Live Production](#section-10-manual-next-steps-for-live-production)

---

## System Architecture & Code Layout

The pipeline automates highlight extraction from GTA gameplay streams/files and schedules high-engagement vertical short-form video posts (YouTube Shorts and Instagram Reels) without incurring recurring AI token costs.

```
+-----------------------------------------------------------------------------------+
| GTA-Auto-Clipper                                                                  |
| - Audio loudness, speech density, and chat reaction signal analysis              |
| - Dynamic facecam tracking & safe 9:16 vertical crop (1080x1920)                  |
| - ASS pop-up captions (English or romanized Hinglish), original audio untouched   |
| - Generates <name>.mp4 + <name>.json (+ <name>.bad veto file on rejection)        |
+------------------------------------------+----------------------------------------+
                                           | Output files (.mp4 + .json)
                                           v
+-----------------------------------------------------------------------------------+
| GTA-Auto-Sender (Feeder)                                                          |
| - Polls Clipper output directory (filters out .bad, test:true, unconfirmed)       |
| - Enforces India timezone (+05:30 IST / Asia/Kolkata)                             |
| - Balances clips equally across configured social media channels                  |
| - Stages eligible clips into queue/<channel>/ready/ with scheduled post times     |
+------------------------------------------+----------------------------------------+
                                           | Staged clips in ready/
                                           v
+-----------------------------------------------------------------------------------+
| GTA-Auto-Sender (Autopost)                                                        |
| - Reads staged clips from queue/<channel>/ready/                                  |
| - Calculates runway schedule (queue/RUNWAY.md)                                    |
| - Uploads and schedules via Zernio API respecting strict daily/hourly rate limits |
| - Moves published clips to queue/<channel>/scheduled/ (zero duplicate posts)     |
+-----------------------------------------------------------------------------------+
```

### Directory Structure
```
GTA-Automation/
├── .venv/                              # Shared Python 3.11 virtual environment
├── README_SETUP.md                     # Comprehensive setup and operations guide
├── GTA-Auto-Clipper/                   # Clipper repository
│   ├── clip.py                         # Main clipping and rendering entry point
│   ├── live_chat.py                    # Live chat collector and reaction scorer
│   ├── player_track.py                 # Facecam/player detection and crop offset
│   ├── models/                         # YuNet ONNX face detection model
│   ├── requirements.txt                # Clipper dependencies
│   ├── tests/                          # Clipper test suite (32 tests)
│   ├── output/                         # Production clip output directory
│   └── test_out/                       # Test clip output directory (from --test)
└── GTA-Auto-Sender/                    # Sender repository
    ├── clip_feeder.py                  # Feeder script (ingests from Clipper output)
    ├── autopost.py                     # Autopost script (uploads to Zernio API)
    ├── common.py                       # Shared helpers, env loader, timezone
    ├── requirements.txt                # Sender dependencies
    ├── config/
    │   ├── channels.json               # Channel limits, India +05:30 timezone, feeder paths
    │   └── channels.example.json       # Template configuration
    ├── .env                            # API secrets (strictly gitignored)
    ├── .env.example                    # Template secrets file
    ├── queue/                          # State, logs, runway, and channel queues
    │   ├── clip_feeder.json            # Ingestion state tracking
    │   ├── RUNWAY.md                   # Visual scheduling runway table
    │   ├── clip_feeder.log             # Feeder execution log
    │   ├── autopost.log                # Autopost execution log
    │   └── channel1/ready/             # Staged clips ready for upload
    ├── scripts/
    │   └── install-tasks.ps1           # Windows Task Scheduler automation installer
    └── tests/                          # Sender test suite (9 tests)
```

---

## Verified Environment & Tool Versions

The following tool versions have been verified during milestone execution:

| Component | Verified Version | Purpose |
|---|---|---|
| **OS** | Windows 10/11 x64 | Host Operating System |
| **Python** | 3.11.9 (amd64) | Shared runtime for Clipper and Sender |
| **FFmpeg** | 9.1-full_build (Gyan.dev) | Video cropping, scaling, audio extraction, libass caption burn |
| **Node.js** | v22.16.0 | System runtime requirement |
| **Git** | 2.51.0.windows.1 | Version control |
| **faster-whisper** | 1.2.1 | Fast local Whisper speech-to-text transcription |
| **ctranslate2** | 4.9.0 | Transformer inference backend for Whisper |
| **opencv-python-headless** | 5.1.0.95 | Facecam detection and computer vision analysis |
| **onnxruntime** | 1.32.0 | YuNet face detection neural network inference |
| **numpy** | 2.4.6 | Numerical audio loudness and array processing |
| **yt-dlp** | 2026.10.26 | Live stream capture engine |
| **requests** | 2.34.2 | HTTP client for Zernio REST API |

---

## Section 1: Prerequisites Installation

Open PowerShell as Administrator (or standard user if winget has user permissions) and install the required tools using `winget`:

```powershell
# 1. Install Python 3.11
winget install --id Python.Python.3.11 -e --accept-source-agreements --accept-package-agreements

# 2. Install Git
winget install --id Git.Git -e --accept-source-agreements --accept-package-agreements

# 3. Install Node.js LTS
winget install --id OpenJS.NodeJS.LTS -e --accept-source-agreements --accept-package-agreements

# 4. Install FFmpeg (Gyan.dev full build with libass and h264 support)
winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
```

### PATH Verification and Refresh
Restart your PowerShell terminal or refresh the current session's PATH:

```powershell
# Refresh PATH in current session
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

# Verify all tools report valid versions:
python --version    # Expected: Python 3.11.x
node -v             # Expected: v20+ or v22+
git --version       # Expected: git version 2.x+
ffmpeg -version     # Expected: ffmpeg version 7.x, 8.x, or 9.x
ffprobe -version    # Expected: ffprobe version 7.x, 8.x, or 9.x
```

> **Note regarding FFmpeg on Windows**:
> Winget installs Gyan.FFmpeg to `$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Gyan.FFmpeg_*\ffmpeg-*\bin`. If `ffmpeg` is not immediately found in your active terminal, create a symbolic link or hardlink into `$env:USERPROFILE\.local\bin` or append the Gyan bin directory directly to your User PATH:
> ```powershell
> [System.Environment]::SetEnvironmentVariable("Path", $env:Path + ";$((Get-Item $env:LOCALAPPDATA\Microsoft\WinGet\Packages\Gyan.FFmpeg_*\ffmpeg-*\bin).FullName)", "User")
> ```

---

## Section 2: Repositories Setup & Directory Structure

Clone both official repositories into the root automation directory `GTA-Automation`:

```powershell
# 1. Navigate to your workspace directory
Set-Location "c:\Users\vivek\OneDrive\Documents\python\clips upload"

# 2. Create the parent folder (if not existing) and enter it
New-Item -ItemType Directory -Force -Path "GTA-Automation"
Set-Location "GTA-Automation"

# 3. Clone both repositories
git clone https://github.com/AnIntellectualBeing/GTA-Auto-Clipper.git
git clone https://github.com/AnIntellectualBeing/GTA-Auto-Sender.git

# 4. Verify directories
Get-ChildItem -Directory
# Output must list: GTA-Auto-Clipper, GTA-Auto-Sender
```

---

## Section 3: Shared Python Virtual Environment (.venv) Setup

Both projects share a single unified `.venv` located at `GTA-Automation\.venv`. This avoids redundant multi-gigabyte package downloads for torch/ctranslate2/faster-whisper and eliminates cross-project version discrepancies.

```powershell
# Ensure you are in the root directory: GTA-Automation
Set-Location "c:\Users\vivek\OneDrive\Documents\python\clips upload\GTA-Automation"

# 1. Create the shared virtual environment
python -m venv .venv

# 2. Upgrade pip
.\.venv\Scripts\python.exe -m pip install --upgrade pip

# 3. Install unified requirements from both repositories
.\.venv\Scripts\python.exe -m pip install -r "GTA-Auto-Clipper\requirements.txt" -r "GTA-Auto-Sender\requirements.txt"

# 4. Verify core C-extensions and packages import cleanly
.\.venv\Scripts\python.exe -c "import faster_whisper, cv2, yt_dlp, requests, numpy, onnxruntime; print('All core modules imported successfully.')"
```

Expected output:
```
All core modules imported successfully.
```

---

## Section 4: GTA-Auto-Clipper Configuration & Local Testing

GTA-Auto-Clipper analyzes video streams or local recordings, detects peaks in player voice/excitement and chat reaction velocity, detects facecams to crop around them, and renders vertical 9:16 video (`1080x1920`) with burned pop-up captions while keeping original audio untouched.

### Pipeline Configuration Parameters
- `--layout fill` (or `--crop`): Fills the vertical 9:16 frame (`1080x1920`), centering gameplay and shifting away from side facecams.
- `--clip-len 30`: Renders clips of exactly ~30 seconds duration.
- `--lead-in 6`: Starts each clip 6 seconds prior to the detected peak moment.
- `--moment-source combined`: Combines live chat signals with audio loudness, speech density, and reaction phrase scoring. When chat is unavailable or testing locally with `--file`, cleanly falls back to audio/speech.
- Captions: Dynamic 3-word pop-up captions (yellow highlight bounce `\c&H00FFFF&`, earlier words white `\c&HFFFFFF&`, remaining words invisible `\alpha&HFF&`). Profane words in captions are masked to protect platform algorithmic reach, but original source audio is preserved strictly untouched (`-c:a aac`).
- Rejection Veto: Any clip `<name>.mp4` can be rejected by creating `<name>.bad` in the output folder.

### Running a Local Test
You can test the entire clipping pipeline locally using a local MP4 recording:

```powershell
Set-Location "c:\Users\vivek\OneDrive\Documents\python\clips upload\GTA-Automation\GTA-Auto-Clipper"

# Execute test clipping run (--test writes to test_out/ and flags metadata as test:true)
..\.venv\Scripts\python.exe clip.py --file test_gameplay.mp4 --test --clip-len 30 --lead-in 6 --layout fill --moment-source combined
```

### Output Media Verification (`ffprobe`)
Verify that the generated clip matches all vertical video specifications:

```powershell
# Verify video stream (Width: 1080, Height: 1920, DAR: 9:16, Codec: h264)
ffprobe -v error -select_streams v:0 -show_entries stream=width,height,codec_name -of default=noprint_wrappers=1 "test_out\gta-20261121-174105-1.mp4"

# Verify audio stream (Codec: aac, Sample Rate: 44100, original audio preserved)
ffprobe -v error -select_streams a:0 -show_entries stream=codec_name,sample_rate,channels -of default=noprint_wrappers=1 "test_out\gta-20261121-174105-1.mp4"
```

### Metadata JSON Verification
Check the accompanying `<name>.json` metadata file:

```powershell
Get-Content "test_out\gta-20261121-174105-1.json"
```

Verified fields must include:
- `"framing": "fill-9x16"`
- `"score": <numeric_score>`
- `"test": true`
- `"gameplay_confirmed": false` (must be `false` unless explicitly confirmed by visual inspection)

### Rejection Veto Verification
To veto a clip from ever being fed into the publishing queue, create a `.bad` file:

```powershell
Set-Content -Path "test_out\gta-20261121-174105-1.bad" -Value "Vetoed: test run clip - manual rejection verification"
```

---

## Section 5: GTA-Auto-Sender Configuration & Credential Security

GTA-Auto-Sender reads finished clips from Clipper, balances them equally across social channels, formats metadata and hashtags, and uploads to YouTube Shorts and Instagram Reels via the Zernio API.

### 1. Configure `config/channels.json`
Copy `config/channels.example.json` to `config/channels.json` and configure:
- India timezone: `"utc_offset": "+05:30"` and `"timezone_name": "Asia/Kolkata"`.
- Rate limits: YouTube: 3/hr, 10/day; Instagram: 1/hr, 45/day.
- Clipper output path: forward slashes `c:/Users/vivek/OneDrive/Documents/python/clips upload/GTA-Automation/GTA-Auto-Clipper/output`.

```powershell
Set-Location "c:\Users\vivek\OneDrive\Documents\python\clips upload\GTA-Automation\GTA-Auto-Sender"

# Create config/channels.json
@'
{
  "utc_offset": "+05:30",
  "timezone_name": "Asia/Kolkata",
  "feeder": {
    "clipper_output": "c:/Users/vivek/OneDrive/Documents/python/clips upload/GTA-Automation/GTA-Auto-Clipper/output",
    "feed_since": "2026-01-01T00:00",
    "lookahead_hours": 2,
    "min_score": 0,
    "credit_label": "Gameplay",
    "site_line": "Clipped with the free GTA Auto Clipper: https://github.com/AnIntellectualBeing/GTA-Auto-Clipper",
    "titles": [
      "This GTA 6 moment is wild",
      "Nobody expected this",
      "Chat went crazy at this one",
      "GTA 6 physics are unreal"
    ],
    "hashtags": [
      "#gta6",
      "#gta",
      "#gaming",
      "#shorts"
    ]
  },
  "channels": {
    "channel1": {
      "key_env": "ZERNIO_KEY_MAIN",
      "youtube_account_id": "PASTE_ZERNIO_YOUTUBE_ACCOUNT_ID",
      "instagram_account_id": "PASTE_ZERNIO_INSTAGRAM_ACCOUNT_ID",
      "youtube_per_hour": 3,
      "instagram_per_hour": 1,
      "youtube_per_day": 10,
      "instagram_per_day": 45,
      "youtube_category": "20"
    },
    "channel2": {
      "key_env": "ZERNIO_KEY_MAIN",
      "youtube_account_id": "PASTE_SECOND_YOUTUBE_ACCOUNT_ID",
      "instagram_account_id": "PASTE_SECOND_INSTAGRAM_ACCOUNT_ID",
      "youtube_per_hour": 3,
      "instagram_per_hour": 1,
      "youtube_per_day": 10,
      "instagram_per_day": 45
    }
  }
}
'@ | Set-Content -Path "config\channels.json" -Encoding UTF8
```

### 2. Configure Credential Security (`.env`)
Create `.env` from template `.env.example`. Never paste real secrets in public chats, commit them to git, or print them in terminal logs:

```powershell
# Create .env from template
@'
# One line per Zernio API key. The name must match "key_env" in config/channels.json.
# Never commit this file (it is in .gitignore). Never paste a key into a public chat.
ZERNIO_KEY_MAIN=placeholder_key_not_set
'@ | Set-Content -Path ".env" -Encoding UTF8
```

### 3. Verify Gitignore Protection
Confirm that secrets and local channel configuration are strictly ignored by Git:

```powershell
git check-ignore -v .env config/channels.json
```
Expected output:
```
.gitignore:1:.env    .env
.gitignore:5:config/channels.json    config/channels.json
```

---

## Section 6: Unit Test Suite Execution

Both repositories feature comprehensive automated test suites covering video processing, moment analysis, ingestion filtering, grid scheduling, and dry-run safety.

### 1. Run Clipper Unit Tests
```powershell
Set-Location "c:\Users\vivek\OneDrive\Documents\python\clips upload\GTA-Automation\GTA-Auto-Clipper"

# Run Clipper test suite
..\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```
Expected output:
```
Ran 32 tests in 0.100s
OK
```

### 2. Run Sender Unit Tests
```powershell
Set-Location "c:\Users\vivek\OneDrive\Documents\python\clips upload\GTA-Automation\GTA-Auto-Sender"

# Run Sender test suite
..\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```
Expected output:
```
Ran 9 tests in ~6.0s
OK
```

---

## Section 7: Dry-Run Verification & Filter Safety Matrix

Dry-run mode (`--dry`) allows you to verify the entire pipeline without making live API calls, uploading videos, or mutating the ready queue.

### Ingestion Filter Safety Matrix
`clip_feeder.py` evaluates every file pair in `GTA-Auto-Clipper/output` through a strict safety filter:

| Condition | Action | Safety Purpose |
|---|---|---|
| `<name>.bad` file present | **VETOED** | Immediate rejection; also purges staged clips from `queue/<channel>/ready/` |
| `"test": true` in JSON | **SKIPPED** | Prevents synthetic/test clips from ever reaching the social queue |
| `"gameplay_confirmed": false` | **SKIPPED** | Prevents unverified streams from publishing |
| `score < min_score` | **SKIPPED** | Enforces minimum quality threshold |
| File age `< 60s` | **HELD** | Prevents reading partial clips while FFmpeg is rendering |

### Running Feeder and Autopost Dry Runs
```powershell
Set-Location "c:\Users\vivek\OneDrive\Documents\python\clips upload\GTA-Automation\GTA-Auto-Sender"

# 1. Test Feeder in dry-run mode
..\.venv\Scripts\python.exe clip_feeder.py --dry

# 2. Test Autopost in dry-run mode
..\.venv\Scripts\python.exe autopost.py --dry

# 3. Inspect the generated visual runway table
Get-Content queue\RUNWAY.md
```

`queue/RUNWAY.md` displays upcoming post slots, queue inventory, and buffer days remaining per channel. In `--dry` mode, zero live HTTP requests are sent to Zernio.

---

## Section 8: Windows Task Scheduler Automation

The PowerShell script `scripts\install-tasks.ps1` sets up two Windows Scheduled Tasks that run every 5 minutes in the background:
- `GtaSenderFeeder`: Runs `clip_feeder.py` to ingest new clips into `ready/`.
- `GtaSenderAutopost`: Runs `autopost.py` to upload staged clips to Zernio.

The script automatically detects the shared `.venv` at `..\.venv\Scripts\pythonw.exe`, quotes paths containing spaces (`clips upload`), sets the working directory to `GTA-Auto-Sender`, and configures automatic retries.

### 1. Inspect Task Plan via Dry Run
```powershell
Set-Location "c:\Users\vivek\OneDrive\Documents\python\clips upload\GTA-Automation\GTA-Auto-Sender"

powershell -ExecutionPolicy Bypass -File scripts\install-tasks.ps1 -DryRun
```
Expected output:
```
Resolved Python: C:\Users\vivek\OneDrive\Documents\python\clips upload\GTA-Automation\.venv\Scripts\pythonw.exe
Sender directory: C:\Users\vivek\OneDrive\Documents\python\clips upload\GTA-Automation\GTA-Auto-Sender
Verifying requirements with: C:\Users\vivek\OneDrive\Documents\python\clips upload\GTA-Automation\.venv\Scripts\python.exe
[DryRun] Task 'GtaSenderFeeder':
  Execute:          C:\Users\vivek\OneDrive\Documents\python\clips upload\GTA-Automation\.venv\Scripts\pythonw.exe
  Argument:         "C:\Users\vivek\OneDrive\Documents\python\clips upload\GTA-Automation\GTA-Auto-Sender\clip_feeder.py"
  WorkingDirectory: C:\Users\vivek\OneDrive\Documents\python\clips upload\GTA-Automation\GTA-Auto-Sender
  Trigger:          Every 5 minutes (repeating)
[DryRun] Task 'GtaSenderAutopost':
  Execute:          C:\Users\vivek\OneDrive\Documents\python\clips upload\GTA-Automation\.venv\Scripts\pythonw.exe
  Argument:         "C:\Users\vivek\OneDrive\Documents\python\clips upload\GTA-Automation\GTA-Auto-Sender\autopost.py"
  WorkingDirectory: C:\Users\vivek\OneDrive\Documents\python\clips upload\GTA-Automation\GTA-Auto-Sender
  Trigger:          Every 5 minutes (repeating)
Dry run complete. No tasks were registered.
```

### 2. Register Scheduled Tasks
```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-tasks.ps1
```
Output:
```
Installed GtaSenderFeeder (every 5 minutes).
Installed GtaSenderAutopost (every 5 minutes).
Done. Check queue\autopost.log and queue\clip_feeder.log after about 6 minutes.
```

### 3. Verify Registered Tasks in Task Scheduler
```powershell
Get-ScheduledTask -TaskName 'GtaSender*'
```
Output:
```
TaskPath                                       TaskName                          State
--------                                       --------                          -----
\                                              GtaSenderAutopost                 Ready
\                                              GtaSenderFeeder                   Ready
```

### 4. Manually Trigger and Inspect Logs
You can manually trigger either task to verify execution without waiting 5 minutes:

```powershell
# Manually start tasks
Start-ScheduledTask -TaskName 'GtaSenderFeeder'
Start-ScheduledTask -TaskName 'GtaSenderAutopost'

# Inspect background execution logs
Get-Content queue\clip_feeder.log -Tail 20
Get-Content queue\autopost.log -Tail 20
```

### 5. Remove Scheduled Tasks
When you need to pause automation, do maintenance, or prevent unattended tasks from running:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-tasks.ps1 -Remove
```
Output:
```
Tasks removed.
```

---

## Section 9: Troubleshooting Guide

### 1. `ffmpeg` or `ffprobe` is not recognized as an internal or external command
- **Cause**: Shell session inherited an older environment before Gyan.FFmpeg was installed via winget.
- **Solution**: Restart your PowerShell window, or add the Gyan bin directory directly:
  ```powershell
  $binPath = (Get-Item "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Gyan.FFmpeg_*\ffmpeg-*\bin").FullName
  $env:Path += ";$binPath"
  ```

### 2. Script arguments break on workspace path containing spaces (`clips upload`)
- **Cause**: Paths like `c:\Users\...\clips upload\...` get parsed into two separate arguments if unquoted.
- **Solution**: Always quote paths in PowerShell:
  `New-ScheduledTaskAction -Execute $py -Argument "`"$scriptFile`"`" -WorkingDirectory $kit`. The updated `install-tasks.ps1` automatically wraps script paths in escaped double quotes.

### 3. `ModuleNotFoundError: No module named 'faster_whisper'` or `cv2`
- **Cause**: Python command was executed using global system Python instead of the shared `.venv`.
- **Solution**: Always invoke python via `..\.venv\Scripts\python.exe` or `.\.venv\Scripts\python.exe`.

### 4. Feeder skips clips without error
- **Cause**: Clip is flagged with `"test": true`, `"gameplay_confirmed": false`, has an accompanying `<name>.bad` file, or the file was modified less than 60 seconds ago (`MIN_AGE`).
- **Solution**: Inspect `<name>.json` to ensure `"gameplay_confirmed": true` and `"test": false` for live production clips, and verify no `.bad` veto file exists in the directory.

### 5. `install-tasks.ps1` fails with Execution Policy Error
- **Cause**: PowerShell script execution is restricted on the machine.
- **Solution**: Run with `-ExecutionPolicy Bypass`:
  ```powershell
  powershell -ExecutionPolicy Bypass -File scripts\install-tasks.ps1
  ```

### 6. Timezone Offset Mismatch in Schedules
- **Cause**: Local machine clock differs from `channels.json` configuration.
- **Solution**: Ensure `"utc_offset": "+05:30"` and `"timezone_name": "Asia/Kolkata"` match your intended posting market (India Standard Time). `common.py` parses ISO-8601 strings with timezone awareness.

---

## Section 10: Manual Next Steps for Live Production

Before switching from testing/dry-run mode to live social media publishing, complete the following manual steps:

1. **Obtain Zernio API Key**:
   - Sign up at Zernio (or your multi-platform social publisher portal).
   - Generate your API secret key.
   - Edit `GTA-Auto-Sender\.env` and replace `placeholder_key_not_set` with your live key:
     ```env
     ZERNIO_KEY_MAIN=your_live_zernio_api_key_here
     ```

2. **Configure Social Channel Account IDs**:
   - In `GTA-Auto-Sender\config\channels.json`, replace:
     - `PASTE_ZERNIO_YOUTUBE_ACCOUNT_ID` with your authenticated YouTube account ID.
     - `PASTE_ZERNIO_INSTAGRAM_ACCOUNT_ID` with your authenticated Instagram account ID.
   - Adjust `youtube_per_day` and `instagram_per_day` if your channel account limits differ.

3. **Configure Live Chat API Key for Stream Capture**:
   - For live YouTube livestream highlight extraction, obtain a Google Cloud YouTube Data API v3 key.
   - Set environment variable `$env:YOUTUBE_API_KEY="your_youtube_api_key"` or configure in Clipper for live chat reaction scoring.

4. **Visually Confirm Gameplay**:
   - When running live capture on a stream, visually verify that the stream is actively displaying GTA gameplay and pass `--gameplay-confirmed`:
     ```powershell
     ..\.venv\Scripts\python.exe clip.py https://youtube.com/live/EXAMPLE_STREAM_ID --clip-len 30 --lead-in 6 --layout fill --moment-source combined --gameplay-confirmed
     ```

5. **Activate Background Tasks**:
   - Once credentials are verified and dry runs succeed, install the scheduled tasks:
     ```powershell
     powershell -ExecutionPolicy Bypass -File scripts\install-tasks.ps1
     ```
   - Monitor `queue/RUNWAY.md`, `queue/clip_feeder.log`, and `queue/autopost.log` during the first week of operation.
