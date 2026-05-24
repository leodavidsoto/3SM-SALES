# AutoShorts — Skill Reference

Daily pipeline that transforms one long-form vertical video into a stream of short-form viral clips,
with mobile-friendly approval and a feedback loop that learns from engagement data.

## What this skill does

1. **Picks** the newest unprocessed video from your input folder
2. **Transcribes** it with Whisper (word-level timestamps, language auto-detected)
3. **Analyzes** the full video + transcript with Gemini Flash to find 3–10 viral moments
4. **Cuts** each candidate with ffmpeg (frame-accurate)
5. **Overlays** a styled hook text (black pill, 78% opacity) via Pillow + ffmpeg
6. **Presents** candidates as a markdown table for your review (absolute file paths for previews)
7. **Publishes** approved clips to TikTok, Instagram Reels, YouTube Shorts via Upload-Post
8. **Learns** weekly from engagement data, updating HOT.md to improve future picks

## Requirements

- Python 3.11+
- `ffmpeg` and `ffprobe` on PATH (`brew install ffmpeg` or `apt install ffmpeg`)
- `pip install faster-whisper google-genai requests python-dotenv Pillow`
- API keys in `.env` (see `.env.example`)
- Videos must be **9:16 vertical** (1080×1920 ideally), ready-to-post with subtitles pre-burned

## Setup

```bash
cp .env.example .env
# Fill in GEMINI_API_KEY, UPLOAD_POST_API_KEY, UPLOAD_POST_PROFILE
pip install -e .
mkdir -p ~/Documents/skill-autoshorts/input
```

## Daily workflow

```bash
# 1. Drop a long video into your input folder, then:
autoshorts pick

# 2. Generate word-level transcript (first run downloads ~1.5 GB Whisper model)
autoshorts transcribe /path/to/video.mp4

# 3. Identify clip candidates via Gemini Flash
autoshorts analyze /path/to/video.mp4

# 4. Cut raw clips
autoshorts extract /path/to/video.mp4

# 5. Add hook text overlay
autoshorts hook /path/to/video.mp4

# 6. Preview frames for QA
autoshorts preview /path/to/video.mp4

# 7. Publish approved clips (staggered, one per day)
autoshorts publish /path/to/video.mp4 clip_01 clip_03

# 8. Mark video as done
autoshorts mark-processed /path/to/video.mp4
```

## Commands reference

| Command | Description |
|---------|-------------|
| `pick` | Select newest unprocessed video from INPUT_FOLDER |
| `transcribe <video>` | Whisper word-level transcript → `output/<slug>/transcript.json` |
| `analyze <video>` | Gemini Flash clip candidates → `output/<slug>/candidates.json` |
| `extract <video> [ids…]` | ffmpeg cut → `output/<slug>/clips/<id>.mp4` |
| `hook <video> [ids…]` | Text overlay → `output/<slug>/finals/<id>.mp4` |
| `preview <video>` | Frame grabs → `output/<slug>/previews/` |
| `publish <video> <ids…>` | Upload-Post schedule → logged to `learnings/post-history.jsonl` |
| `mark-processed <video>` | SHA256-track in `state/processed.json` |
| `learn` | Pull analytics, compute z-scores, update `learnings/HOT.md` |
| `reflect <video>` | Compare offered vs. approved, extract creator taste patterns |

## File structure

```
~/Documents/skill-autoshorts/
├── input/                        ← drop long-form videos here
├── output/
│   └── <video_slug>/
│       ├── transcript.json       ← Whisper word timestamps
│       ├── candidates.json       ← Gemini clip proposals
│       ├── clips/                ← raw cuts
│       ├── finals/               ← cuts + hook overlay
│       └── previews/             ← QA frames
├── state/
│   └── processed.json            ← sha256 → slug mapping
└── learnings/
    ├── HOT.md                    ← current performance patterns
    ├── post-history.jsonl        ← publish log
    └── metrics_YYYY-MM-DD.json   ← analytics snapshots
```

## Learning loop

Run `autoshorts learn` weekly (needs ≥10 posts aged 7–90 days).
It fetches engagement data from Upload-Post, computes composite z-scores
(0.6 × views + 0.4 × engagement_rate), identifies top/bottom 20%,
and asks Gemini to synthesize patterns → HOT.md.

HOT.md is automatically prepended to every future `analyze` prompt,
so the AI learns what performs well for your specific audience.

## Platform notes

- **TikTok**: defaults to `MEDIA_UPLOAD` (draft). Use `--tiktok-mode direct` to publish immediately.
- **Instagram**: requires Business/Creator account linked to a Facebook Page.
- **Upload-Post free tier**: 10 uploads/month (1 clip × 3 platforms = 3 uploads).

## Platform copy targets

| Platform | Title/caption |
|----------|---------------|
| YouTube  | 40–60 chars, SEO keywords |
| TikTok   | 70–85 chars, 1–2 emojis, hashtags |
| Instagram | Long-form caption 500–800 chars + 20–30 hashtags |
