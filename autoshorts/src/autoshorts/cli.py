#!/usr/bin/env python3
"""autoshorts CLI — pick → transcribe → analyze → extract → hook → publish → learn."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import statistics
import subprocess
import sys
import textwrap
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

# ── Configuration ──────────────────────────────────────────────────────────────

_DEFAULT_BASE = Path.home() / "Documents" / "skill-autoshorts"

INPUT_FOLDER = Path(os.getenv("INPUT_FOLDER", str(_DEFAULT_BASE / "input")))
OUTPUT_FOLDER = Path(os.getenv("OUTPUT_FOLDER", str(_DEFAULT_BASE / "output")))
STATE_FILE = _DEFAULT_BASE / "state" / "processed.json"
LEARNINGS_DIR = _DEFAULT_BASE / "learnings"
HOT_MD = LEARNINGS_DIR / "HOT.md"
POST_HISTORY = LEARNINGS_DIR / "post-history.jsonl"

GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
UPLOAD_POST_API_KEY: str = os.getenv("UPLOAD_POST_API_KEY", "")
UPLOAD_POST_PROFILE: str = os.getenv("UPLOAD_POST_PROFILE", "")
WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "medium")

UPLOAD_POST_BASE = "https://v1.uploadpost.app"
GEMINI_MODEL = "gemini-2.0-flash"

VIDEO_EXTS = {".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v"}
PLATFORMS = ["youtube", "tiktok", "instagram"]

# ── Utility helpers ────────────────────────────────────────────────────────────


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65_536), b""):
            h.update(chunk)
    return h.hexdigest()


def slug_from_path(path: Path) -> str:
    slug = re.sub(r"[^\w\-]", "_", path.stem).strip("_")
    return slug or "video"


def load_processed() -> dict[str, str]:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_processed(data: dict[str, str]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(data, indent=2))


def output_dir(video: Path) -> Path:
    d = OUTPUT_FOLDER / slug_from_path(video)
    d.mkdir(parents=True, exist_ok=True)
    return d


def hot_md_content() -> str:
    return HOT_MD.read_text() if HOT_MD.exists() else ""


def append_post_history(record: dict) -> None:
    LEARNINGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(POST_HISTORY, "a") as f:
        f.write(json.dumps(record) + "\n")


def require_env(*keys: str) -> None:
    missing = [k for k in keys if not os.getenv(k)]
    if missing:
        print(f"ERROR: Missing required env vars: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)


def run_ffmpeg(cmd: list[str]) -> bool:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ffmpeg error: {result.stderr[-400:]}", file=sys.stderr)
        return False
    return True


def video_duration(path: Path) -> float:
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(path)],
        capture_output=True,
        text=True,
    )
    try:
        return float(json.loads(probe.stdout)["format"]["duration"])
    except Exception:
        return 0.0


def video_dimensions(path: Path) -> tuple[int, int]:
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", str(path)],
        capture_output=True,
        text=True,
    )
    try:
        streams = json.loads(probe.stdout)["streams"]
        vid = next(s for s in streams if s["codec_type"] == "video")
        return int(vid["width"]), int(vid["height"])
    except Exception:
        return 1080, 1920


# ── pick ───────────────────────────────────────────────────────────────────────


def cmd_pick(_args: argparse.Namespace) -> None:
    """Select the newest unprocessed video from INPUT_FOLDER."""
    INPUT_FOLDER.mkdir(parents=True, exist_ok=True)

    videos = [p for p in INPUT_FOLDER.iterdir() if p.suffix.lower() in VIDEO_EXTS]
    if not videos:
        print(f"No video files in {INPUT_FOLDER}. Drop long-form vertical videos there.")
        return

    processed = load_processed()
    videos.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    for video in videos:
        sha = sha256_file(video)
        if sha in processed:
            continue
        print(f"PICKED:  {video}")
        print(f"SHA256:  {sha}")
        print(f"Slug:    {slug_from_path(video)}")
        print(f"\nNext step:\n  autoshorts transcribe \"{video}\"")
        return

    print("All videos already processed. Drop new content in:", INPUT_FOLDER)


# ── transcribe ─────────────────────────────────────────────────────────────────


def cmd_transcribe(args: argparse.Namespace) -> None:
    """Generate word-level transcript using faster-whisper."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("ERROR: faster-whisper not installed. Run: pip install faster-whisper", file=sys.stderr)
        sys.exit(1)

    video = Path(args.video)
    if not video.exists():
        print(f"ERROR: File not found: {video}", file=sys.stderr)
        sys.exit(1)

    out = output_dir(video)
    transcript_path = out / "transcript.json"

    print(f"Loading Whisper model '{WHISPER_MODEL}' (first run downloads ~1.5 GB)…")
    model = WhisperModel(WHISPER_MODEL, compute_type="int8")

    print("Transcribing…")
    segments_iter, info = model.transcribe(
        str(video),
        word_timestamps=True,
        language=getattr(args, "language", None) or None,
    )

    words: list[dict] = []
    segments_out: list[dict] = []

    for seg in segments_iter:
        seg_words: list[dict] = []
        if seg.words:
            for w in seg.words:
                rec = {
                    "word": w.word,
                    "start": round(w.start, 3),
                    "end": round(w.end, 3),
                    "probability": round(w.probability, 3),
                }
                words.append(rec)
                seg_words.append(rec)
        segments_out.append(
            {
                "id": seg.id,
                "start": round(seg.start, 3),
                "end": round(seg.end, 3),
                "text": seg.text.strip(),
                "words": seg_words,
            }
        )

    transcript = {
        "language": info.language,
        "duration": round(info.duration, 3),
        "segments": segments_out,
        "words": words,
    }
    transcript_path.write_text(json.dumps(transcript, indent=2, ensure_ascii=False))

    print(f"Transcript saved: {transcript_path}")
    print(f"Language: {info.language} | Duration: {info.duration:.1f}s | Words: {len(words)}")
    print(f"\nNext step:\n  autoshorts analyze \"{video}\"")


# ── analyze ────────────────────────────────────────────────────────────────────


def cmd_analyze(args: argparse.Namespace) -> None:
    """Identify viral clip candidates using Gemini Flash multimodal analysis."""
    require_env("GEMINI_API_KEY")

    try:
        from google import genai
        from google.genai import types as gtypes
    except ImportError:
        print("ERROR: google-genai not installed. Run: pip install google-genai", file=sys.stderr)
        sys.exit(1)

    video = Path(args.video)
    out = output_dir(video)
    transcript_path = out / "transcript.json"
    candidates_path = out / "candidates.json"

    if not transcript_path.exists():
        print("ERROR: Transcript not found. Run 'transcribe' first.", file=sys.stderr)
        sys.exit(1)

    transcript = json.loads(transcript_path.read_text())
    words_text = " ".join(w["word"] for w in transcript["words"])
    duration = transcript["duration"]

    hot = hot_md_content()
    hot_section = f"\n\n## LEARNINGS FROM PAST PERFORMANCE (HOT.md)\n{hot}\n" if hot else ""

    system_prompt = textwrap.dedent(
        f"""
        You are a short-form video strategist specializing in viral content for TikTok,
        Instagram Reels, and YouTube Shorts. Analyze this video + transcript to find
        every moment that could become a standalone viral clip.
        {hot_section}
        CONSTRAINTS:
        - Each clip must be 20–60 seconds long (strictly enforced).
        - Snap cut boundaries to word boundaries from the transcript.
        - Never cut mid-sentence; prefer natural pauses or breath marks.
        - Clips must be self-contained (viewer needs zero prior context).
        - First 3 seconds must hook attention.
        - Return 3–10 candidates ordered by viral potential (highest first).
        - hook_text: 3–7 words shown as text overlay (title case, punchy).

        Return ONLY valid JSON — no markdown fences, no commentary:
        [
          {{
            "id": "clip_01",
            "start": 12.4,
            "end": 47.2,
            "hook_text": "Nobody Tells You This",
            "score": 0.95,
            "rationale": "Strong emotional hook, complete story arc, surprising reveal."
          }}
        ]
        """
    ).strip()

    client = genai.Client(api_key=GEMINI_API_KEY)

    print("Uploading video to Gemini Files API (30–60s for a 9-min video)…")
    uploaded = client.files.upload(path=str(video))

    # Wait for Gemini to finish processing the file
    for attempt in range(40):
        file_info = client.files.get(name=uploaded.name)
        state = file_info.state.name
        if state == "ACTIVE":
            break
        if state == "FAILED":
            print("ERROR: Gemini file processing failed.", file=sys.stderr)
            sys.exit(1)
        print(f"  Processing… ({attempt + 1}/40)")
        time.sleep(3)
    else:
        print("ERROR: Gemini file processing timed out.", file=sys.stderr)
        sys.exit(1)

    transcript_ctx = f"Video duration: {duration:.1f}s\n\nTranscript:\n{words_text[:10_000]}"

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            gtypes.Part.from_uri(file_uri=uploaded.uri, mime_type=uploaded.mime_type),
            transcript_ctx,
            system_prompt,
        ],
    )

    raw = response.text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        candidates = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"ERROR: Gemini returned invalid JSON: {exc}", file=sys.stderr)
        print(f"Raw response (first 500 chars): {raw[:500]}", file=sys.stderr)
        sys.exit(1)

    valid: list[dict] = []
    for c in candidates:
        clip_dur = c["end"] - c["start"]
        if not (15 <= clip_dur <= 65):
            print(f"  Skipping {c['id']}: duration {clip_dur:.1f}s outside 20–60s window")
            continue
        if c["start"] < 0 or c["end"] > duration + 1:
            print(f"  Skipping {c['id']}: timestamps out of video bounds")
            continue
        valid.append(c)

    candidates_path.write_text(json.dumps(valid, indent=2, ensure_ascii=False))

    # Clean up Gemini file upload
    try:
        client.files.delete(name=uploaded.name)
    except Exception:
        pass

    print(f"\nCandidates saved: {candidates_path}")
    print(f"Found {len(valid)} valid candidates:\n")
    for c in valid:
        dur = c["end"] - c["start"]
        print(
            f"  [{c['id']}] {c['start']:.1f}s–{c['end']:.1f}s "
            f"({dur:.0f}s) score={c['score']:.2f} | {c['hook_text']}"
        )
    print(f"\nNext step:\n  autoshorts extract \"{video}\"")


# ── extract ────────────────────────────────────────────────────────────────────


def cmd_extract(args: argparse.Namespace) -> None:
    """Cut raw clips using ffmpeg with frame-accurate seeking."""
    video = Path(args.video)
    out = output_dir(video)
    candidates_path = out / "candidates.json"

    if not candidates_path.exists():
        print("ERROR: Run 'analyze' first.", file=sys.stderr)
        sys.exit(1)

    candidates: list[dict] = json.loads(candidates_path.read_text())
    ids = set(args.ids) if args.ids else None
    clips_dir = out / "clips"
    clips_dir.mkdir(exist_ok=True)

    for c in candidates:
        if ids and c["id"] not in ids:
            continue
        duration = c["end"] - c["start"]
        clip_out = clips_dir / f"{c['id']}.mp4"
        print(f"Cutting {c['id']}: {c['start']:.1f}s–{c['end']:.1f}s ({duration:.0f}s)")
        ok = run_ffmpeg(
            [
                "ffmpeg", "-y",
                "-ss", str(c["start"]),
                "-i", str(video),
                "-t", str(duration),
                "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart",
                str(clip_out),
            ]
        )
        if ok:
            print(f"  → {clip_out}")

    print(f"\nNext step:\n  autoshorts hook \"{video}\"")


# ── hook ───────────────────────────────────────────────────────────────────────


def _render_hook_frame(frame_path: Path, hook_text: str, out_path: Path) -> None:
    """Draw styled hook text (black pill, 78% opacity) onto a frame image."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.open(frame_path).convert("RGBA")
    W, H = img.size
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font_size = max(42, W // 18)
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont = ImageFont.load_default()
    for candidate_path in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]:
        if Path(candidate_path).exists():
            font = ImageFont.truetype(candidate_path, font_size)
            break

    max_chars = max(12, W // (font_size // 2))
    lines = textwrap.wrap(hook_text.upper(), width=max_chars) or [hook_text.upper()]

    line_h = font_size + 12
    pad_x, pad_y, radius = 32, 20, 24
    # Pill opacity: 78% → 199/255
    PILL_FILL = (0, 0, 0, 199)
    y = int(H * 0.17)

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        x = (W - tw) // 2
        draw.rounded_rectangle(
            [x - pad_x, y - pad_y, x + tw + pad_x, y + th + pad_y],
            radius=radius,
            fill=PILL_FILL,
        )
        # Thin black stroke for legibility
        for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
            draw.text((x + dx, y + dy), line, font=font, fill=(0, 0, 0, 255))
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
        y += line_h

    Image.alpha_composite(img, overlay).convert("RGB").save(str(out_path), quality=95)


def cmd_hook(args: argparse.Namespace) -> None:
    """Overlay styled hook text onto clips using Pillow + ffmpeg."""
    video = Path(args.video)
    out = output_dir(video)
    candidates_path = out / "candidates.json"

    if not candidates_path.exists():
        print("ERROR: Run 'analyze' then 'extract' first.", file=sys.stderr)
        sys.exit(1)

    candidates: list[dict] = json.loads(candidates_path.read_text())
    ids = set(args.ids) if args.ids else None
    clips_dir = out / "clips"
    finals_dir = out / "finals"
    finals_dir.mkdir(exist_ok=True)
    tmp_dir = out / "_hook_tmp"
    tmp_dir.mkdir(exist_ok=True)

    try:
        for c in candidates:
            if ids and c["id"] not in ids:
                continue
            clip_path = clips_dir / f"{c['id']}.mp4"
            if not clip_path.exists():
                print(f"  Skipping {c['id']}: clip missing (run extract first)")
                continue

            final_path = finals_dir / f"{c['id']}.mp4"
            hook = c["hook_text"]
            print(f"Adding hook \"{hook}\" to {c['id']}…")

            frame_path = tmp_dir / f"{c['id']}_frame.png"
            run_ffmpeg(["ffmpeg", "-y", "-i", str(clip_path), "-vframes", "1",
                        "-q:v", "2", str(frame_path)])
            if not frame_path.exists():
                print(f"  ERROR: Could not extract frame from {clip_path}", file=sys.stderr)
                continue

            overlay_img = tmp_dir / f"{c['id']}_overlay.png"
            _render_hook_frame(frame_path, hook, overlay_img)

            W, H = video_dimensions(clip_path)
            overlay_resized = tmp_dir / f"{c['id']}_overlay_r.png"
            run_ffmpeg(["ffmpeg", "-y", "-i", str(overlay_img),
                        "-vf", f"scale={W}:{H}", str(overlay_resized)])

            # Show hook overlay for first 5s (or full clip if shorter)
            hook_dur = min(video_duration(clip_path), 5.0)
            ok = run_ffmpeg(
                [
                    "ffmpeg", "-y",
                    "-i", str(clip_path),
                    "-i", str(overlay_resized),
                    "-filter_complex",
                    f"[0:v][1:v]overlay=0:0:enable='lte(t,{hook_dur})'[v]",
                    "-map", "[v]",
                    "-map", "0:a?",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                    "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart",
                    str(final_path),
                ]
            )
            if ok:
                print(f"  → {final_path}")
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print(f"\nNext step:\n  autoshorts preview \"{video}\"")


# ── preview ────────────────────────────────────────────────────────────────────


def cmd_preview(args: argparse.Namespace) -> None:
    """Extract frames from finals for visual QA review."""
    video = Path(args.video)
    out = output_dir(video)
    finals_dir = out / "finals"
    clips_dir = out / "clips"
    previews_dir = out / "previews"
    previews_dir.mkdir(exist_ok=True)

    clips = list(finals_dir.glob("*.mp4")) if finals_dir.exists() else []
    if not clips:
        clips = list(clips_dir.glob("*.mp4")) if clips_dir.exists() else []
    if not clips:
        print("No clips found. Run extract (and optionally hook) first.")
        return

    n_frames: int = args.frames or 3

    for clip in sorted(clips):
        dur = video_duration(clip)
        if dur <= 0:
            continue
        print(f"\nPreviewing {clip.name} ({dur:.1f}s):")
        for i in range(n_frames):
            t = dur * (i + 1) / (n_frames + 1)
            frame_out = previews_dir / f"{clip.stem}_f{i + 1:02d}.jpg"
            run_ffmpeg(
                ["ffmpeg", "-y", "-ss", str(t), "-i", str(clip),
                 "-vframes", "1", "-q:v", "3", str(frame_out)]
            )
            if frame_out.exists():
                print(f"  {frame_out}")

    print(f"\nReview the previews above, then publish approved clips:")
    print(f"  autoshorts publish \"{video}\" clip_01 clip_02 …")


# ── publish ────────────────────────────────────────────────────────────────────


def _platform_metadata(candidate: dict) -> dict[str, dict[str, str]]:
    hook = candidate.get("hook_text", "clip")
    rationale = candidate.get("rationale", "")
    return {
        "youtube": {
            "title": hook[:60],
            "caption": f"{hook}. {rationale}"[:300],
        },
        "tiktok": {
            "title": hook[:85],
            "caption": f"{hook} 🔥 #viral #shorts #fyp #trending",
        },
        "instagram": {
            "title": hook[:125],
            "caption": (
                f"{hook}\n\n{rationale}\n\n"
                "#reels #viral #shorts #content #fyp #trending "
                "#explore #motivation #video"
            ),
        },
    }


def cmd_publish(args: argparse.Namespace) -> None:
    """Schedule approved clips to social platforms via Upload-Post API."""
    require_env("UPLOAD_POST_API_KEY", "UPLOAD_POST_PROFILE")

    video = Path(args.video)
    out = output_dir(video)
    candidates_path = out / "candidates.json"
    finals_dir = out / "finals"

    if not candidates_path.exists():
        print("ERROR: Run 'analyze' first.", file=sys.stderr)
        sys.exit(1)

    candidates: list[dict] = json.loads(candidates_path.read_text())
    cand_map = {c["id"]: c for c in candidates}
    platforms: list[str] = args.platforms or PLATFORMS
    tiktok_mode: str = args.tiktok_mode or "MEDIA_UPLOAD"

    auth_headers = {"Authorization": f"Bearer {UPLOAD_POST_API_KEY}"}

    # Stagger: one clip per day, starting tomorrow at noon UTC
    base_dt = (datetime.now(timezone.utc) + timedelta(days=1)).replace(
        hour=12, minute=0, second=0, microsecond=0
    )

    for day_offset, cid in enumerate(args.ids):
        if cid not in cand_map:
            print(f"WARNING: '{cid}' not in candidates — skipping.")
            continue

        cand = cand_map[cid]
        final_path = finals_dir / f"{cid}.mp4"
        if not final_path.exists():
            final_path = out / "clips" / f"{cid}.mp4"
        if not final_path.exists():
            print(f"ERROR: No file found for {cid}. Run extract/hook first.", file=sys.stderr)
            continue

        schedule_dt = base_dt + timedelta(days=day_offset)
        meta = _platform_metadata(cand)
        hook = cand.get("hook_text", cid)

        print(f"\n[{cid}] Uploading file to Upload-Post CDN…")
        with open(final_path, "rb") as fh:
            upload_resp = requests.post(
                f"{UPLOAD_POST_BASE}/upload",
                headers=auth_headers,
                files={"file": (final_path.name, fh, "video/mp4")},
                timeout=120,
            )

        if upload_resp.status_code not in (200, 201):
            print(f"  ERROR uploading: {upload_resp.status_code} {upload_resp.text[:200]}", file=sys.stderr)
            continue

        video_url = (upload_resp.json().get("url") or upload_resp.json().get("video_url", ""))
        if not video_url:
            print(f"  ERROR: No URL in upload response: {upload_resp.text[:200]}", file=sys.stderr)
            continue

        for platform in platforms:
            payload: dict = {
                "profile": UPLOAD_POST_PROFILE,
                "platform": platform,
                "video_url": video_url,
                "title": meta[platform]["title"],
                "caption": meta[platform]["caption"],
                "scheduled_at": schedule_dt.isoformat(),
            }
            if platform == "tiktok":
                payload["upload_type"] = tiktok_mode

            schedule_resp = requests.post(
                f"{UPLOAD_POST_BASE}/schedule",
                headers={**auth_headers, "Content-Type": "application/json"},
                json=payload,
                timeout=30,
            )

            if schedule_resp.status_code in (200, 201):
                post_id = schedule_resp.json().get("id") or schedule_resp.json().get("post_id", "?")
                print(f"  ✓ {platform}: scheduled {schedule_dt.date()} (id={post_id})")
                append_post_history(
                    {
                        "candidate_id": cid,
                        "video_slug": slug_from_path(video),
                        "platform": platform,
                        "post_id": str(post_id),
                        "hook_text": hook,
                        "scheduled_at": schedule_dt.isoformat(),
                        "score": cand.get("score"),
                    }
                )
            else:
                print(
                    f"  ERROR {platform}: {schedule_resp.status_code} {schedule_resp.text[:200]}",
                    file=sys.stderr,
                )


# ── mark-processed ─────────────────────────────────────────────────────────────


def cmd_mark_processed(args: argparse.Namespace) -> None:
    """Record video as fully consumed so 'pick' skips it."""
    video = Path(args.video)
    if not video.exists():
        print(f"ERROR: File not found: {video}", file=sys.stderr)
        sys.exit(1)
    processed = load_processed()
    sha = sha256_file(video)
    processed[sha] = slug_from_path(video)
    save_processed(processed)
    print(f"Marked processed: {video.name} (sha256={sha[:12]}…)")


# ── learn ──────────────────────────────────────────────────────────────────────


def cmd_learn(_args: argparse.Namespace) -> None:
    """Fetch engagement analytics from Upload-Post and synthesize HOT.md via Gemini."""
    require_env("GEMINI_API_KEY", "UPLOAD_POST_API_KEY")

    try:
        from google import genai
    except ImportError:
        print("ERROR: google-genai not installed.", file=sys.stderr)
        sys.exit(1)

    if not POST_HISTORY.exists():
        print("No post-history.jsonl found. Publish clips first, then run learn after 7 days.")
        return

    posts = [
        json.loads(line)
        for line in POST_HISTORY.read_text().splitlines()
        if line.strip()
    ]

    # Soak window: 7–90 days old only
    now = datetime.now(timezone.utc)
    eligible: list[dict] = []
    for p in posts:
        try:
            pub_dt = datetime.fromisoformat(p["scheduled_at"].replace("Z", "+00:00"))
            age = (now - pub_dt).days
            if 7 <= age <= 90:
                eligible.append(p)
        except Exception:
            continue

    if len(eligible) < 10:
        print(
            f"Need ≥10 posts in the 7–90 day soak window; currently {len(eligible)}. "
            "Keep publishing and check back later."
        )
        return

    # Pull analytics for each eligible post
    auth_headers = {"Authorization": f"Bearer {UPLOAD_POST_API_KEY}"}
    metrics: list[dict] = []
    for p in eligible:
        post_id = p.get("post_id")
        if not post_id:
            continue
        try:
            resp = requests.get(
                f"{UPLOAD_POST_BASE}/analytics/{post_id}",
                headers=auth_headers,
                timeout=15,
            )
            if resp.status_code == 200:
                m = resp.json()
                metrics.append(
                    {
                        **p,
                        "views": int(m.get("views", 0)),
                        "likes": int(m.get("likes", 0)),
                        "comments": int(m.get("comments", 0)),
                        "shares": int(m.get("shares", 0)),
                        "engagement_rate": float(m.get("engagement_rate", 0.0)),
                    }
                )
        except Exception as exc:
            print(f"  WARNING: metrics fetch failed for {post_id}: {exc}")

    if len(metrics) < 10:
        print(f"Only {len(metrics)} posts have analytics data. Need ≥10 to synthesize patterns.")
        return

    # Composite z-score: 0.6 × views_z + 0.4 × engagement_z
    views_list = [m["views"] for m in metrics]
    eng_list = [m["engagement_rate"] for m in metrics]
    v_mean = statistics.mean(views_list)
    v_std = statistics.stdev(views_list) or 1.0
    e_mean = statistics.mean(eng_list)
    e_std = statistics.stdev(eng_list) or 1.0

    for m in metrics:
        v_z = (m["views"] - v_mean) / v_std
        e_z = (m["engagement_rate"] - e_mean) / e_std
        m["composite"] = round(0.6 * v_z + 0.4 * e_z, 3)

    metrics.sort(key=lambda m: m["composite"], reverse=True)
    n = len(metrics)
    cutoff = max(1, n // 5)
    top = metrics[:cutoff]
    bottom = metrics[n - cutoff :]

    # Save dated metrics file
    LEARNINGS_DIR.mkdir(parents=True, exist_ok=True)
    metrics_path = LEARNINGS_DIR / f"metrics_{date.today().isoformat()}.json"
    metrics_path.write_text(json.dumps(metrics, indent=2))
    print(f"Metrics saved: {metrics_path}")

    # Synthesize patterns with Gemini
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = textwrap.dedent(
        f"""
        Analyze these short-form clip performance results and extract clear, actionable patterns.

        TOP 20% PERFORMERS:
        {json.dumps(top, indent=2)}

        BOTTOM 20% PERFORMERS:
        {json.dumps(bottom, indent=2)}

        Write a concise HOT.md document with:
        ## WHAT WORKS
        - 3–5 specific bullets about winning hook styles, topics, clip structure, timing

        ## WHAT FAILS
        - 2–3 specific bullets about patterns to avoid

        ## NEXT BATCH RECOMMENDATION
        - 1–2 sentences on what to optimize next

        Keep it under 350 words. Be specific and use examples from the data.
        """
    ).strip()

    response = client.models.generate_content(model=GEMINI_MODEL, contents=[prompt])
    new_content = f"# HOT.md — Updated {date.today().isoformat()}\n\n{response.text.strip()}\n"

    if HOT_MD.exists():
        backup = LEARNINGS_DIR / f"HOT_{date.today().isoformat()}.md.bak"
        backup.write_text(HOT_MD.read_text())
        print(f"Backed up: {backup}")

    HOT_MD.write_text(new_content)
    print(f"HOT.md updated: {HOT_MD}\n")
    print(new_content)


# ── reflect ────────────────────────────────────────────────────────────────────


def cmd_reflect(args: argparse.Namespace) -> None:
    """Qualitative analysis of creator approval decisions to refine future picks."""
    require_env("GEMINI_API_KEY")

    try:
        from google import genai
    except ImportError:
        print("ERROR: google-genai not installed.", file=sys.stderr)
        sys.exit(1)

    video = Path(args.video)
    out = output_dir(video)
    candidates_path = out / "candidates.json"

    if not candidates_path.exists():
        print("ERROR: No candidates found for this video.", file=sys.stderr)
        sys.exit(1)

    candidates: list[dict] = json.loads(candidates_path.read_text())

    published_ids: set[str] = set()
    if POST_HISTORY.exists():
        slug = slug_from_path(video)
        for line in POST_HISTORY.read_text().splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("video_slug") == slug:
                published_ids.add(rec["candidate_id"])

    approved = [c for c in candidates if c["id"] in published_ids]
    rejected = [c for c in candidates if c["id"] not in published_ids]

    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = textwrap.dedent(
        f"""
        A video creator reviewed these short-form clip candidates and chose which to publish.

        ALL CANDIDATES (Gemini-proposed):
        {json.dumps(candidates, indent=2)}

        APPROVED (published by creator):
        {json.dumps(approved, indent=2)}

        REJECTED (skipped by creator):
        {json.dumps(rejected, indent=2)}

        What does this reveal about the creator's taste, quality bar, and audience strategy?
        List 3–5 specific, actionable bullets for future clip selection.
        Focus on what the AI missed or overvalued.
        """
    ).strip()

    response = client.models.generate_content(model=GEMINI_MODEL, contents=[prompt])
    reflection = response.text.strip()

    print("\n## Reflect — Creator Taste Analysis\n")
    print(reflection)

    if args.update_hot:
        existing = HOT_MD.read_text() if HOT_MD.exists() else ""
        LEARNINGS_DIR.mkdir(parents=True, exist_ok=True)
        HOT_MD.write_text(
            existing + f"\n\n## Reflect — {date.today().isoformat()}\n{reflection}\n"
        )
        print(f"\nAppended to: {HOT_MD}")


# ── Argument parser ────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="autoshorts",
        description=(
            "Daily viral-clip pipeline: Whisper + Gemini Flash + Upload-Post.\n"
            "Picks one long video per day, cuts the best moments, and publishes to social."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="command", required=True, metavar="<command>")

    sub.add_parser("pick", help="Select newest unprocessed video from INPUT_FOLDER")

    t = sub.add_parser("transcribe", help="Generate word-level transcript via Whisper")
    t.add_argument("video", help="Path to video file")
    t.add_argument("--language", help="Force language code (e.g. es, en, fr)")

    a = sub.add_parser("analyze", help="Identify viral clip candidates via Gemini Flash")
    a.add_argument("video", help="Path to video file")

    e = sub.add_parser("extract", help="Cut clips with ffmpeg")
    e.add_argument("video", help="Path to video file")
    e.add_argument("ids", nargs="*", help="Clip IDs to extract (default: all)")

    h = sub.add_parser("hook", help="Add styled text overlay to clips")
    h.add_argument("video", help="Path to video file")
    h.add_argument("ids", nargs="*", help="Clip IDs (default: all)")

    pr = sub.add_parser("preview", help="Extract frames for QA review")
    pr.add_argument("video", help="Path to video file")
    pr.add_argument("--frames", type=int, default=3, help="Frames per clip (default: 3)")

    pub = sub.add_parser("publish", help="Schedule clips to social platforms")
    pub.add_argument("video", help="Path to video file")
    pub.add_argument("ids", nargs="+", help="Clip IDs to publish")
    pub.add_argument(
        "--platforms", nargs="+", choices=PLATFORMS,
        help="Target platforms (default: youtube tiktok instagram)"
    )
    pub.add_argument(
        "--tiktok-mode", choices=["MEDIA_UPLOAD", "direct"],
        default="MEDIA_UPLOAD", help="TikTok publish mode (default: MEDIA_UPLOAD = draft)"
    )

    mp = sub.add_parser("mark-processed", help="Mark video as consumed; pick will skip it")
    mp.add_argument("video", help="Path to video file")

    sub.add_parser("learn", help="Fetch analytics and update HOT.md (weekly)")

    ref = sub.add_parser("reflect", help="Qualitative analysis of approved vs. rejected clips")
    ref.add_argument("video", help="Path to video file")
    ref.add_argument("--update-hot", action="store_true", help="Append reflection to HOT.md")

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "pick": cmd_pick,
        "transcribe": cmd_transcribe,
        "analyze": cmd_analyze,
        "extract": cmd_extract,
        "hook": cmd_hook,
        "preview": cmd_preview,
        "publish": cmd_publish,
        "mark-processed": cmd_mark_processed,
        "learn": cmd_learn,
        "reflect": cmd_reflect,
    }

    dispatch[args.command](args)


if __name__ == "__main__":
    main()
