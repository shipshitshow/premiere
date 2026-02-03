"""Viral clip detection and generation."""

import json
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from premiere.generators.transcription import Transcript, save_transcript
from premiere.utils.claude_cli import find_viral_clips, generate_clip_metadata
from premiere.utils.config import get_temp_dir
from premiere.utils.ffmpeg import probe, run_ffmpeg
from premiere.utils.logger import get_logger


@dataclass
class ClipCandidate:
    """A potential viral clip."""

    start: float  # seconds
    end: float  # seconds
    duration: float
    hook: str
    score: int  # 1-10
    caption: str
    reason: str


@dataclass
class GeneratedClip:
    """A generated clip file."""

    path: Path
    start: float
    end: float
    title: str
    caption: str
    hashtags: list[str]
    transcript: str


def detect_viral_moments(
    transcript: Transcript,
    video_duration: float,
    max_clips: int = 5,
    min_duration: int = 15,
    max_duration: int = 60,
) -> list[ClipCandidate]:
    """Detect viral clip candidates from transcript using AI.

    Args:
        transcript: Video transcript.
        video_duration: Total video duration in seconds.
        max_clips: Maximum clips to find.
        min_duration: Minimum clip duration in seconds.
        max_duration: Maximum clip duration in seconds.

    Returns:
        List of clip candidates ranked by viral potential.
    """
    logger = get_logger()
    logger.info(f"Detecting viral moments (max {max_clips} clips)")

    # Save transcript to workspace temp file for Claude CLI
    temp_base = get_temp_dir()
    temp_path = temp_base / f"clips_{int(time.time())}"
    temp_path.mkdir(parents=True, exist_ok=True)
    transcript_path = temp_path / "transcript.md"
    
    try:
        save_transcript(transcript, transcript_path, format="md")

        # Get Claude's analysis
        response = find_viral_clips(
            transcript_path,
            video_duration,
            max_clips,
            (min_duration, max_duration),
        )
    finally:
        # Clean up temp directory
        if temp_path.exists():
            shutil.rmtree(temp_path, ignore_errors=True)

    # Parse response
    clips = _parse_clip_response(response)
    logger.info(f"Found {len(clips)} viral clip candidates")

    return clips


def _parse_clip_response(response: str) -> list[ClipCandidate]:
    """Parse Claude's clip detection response."""
    clips = []

    # Split by CLIP markers
    clip_sections = re.split(r"CLIP\s*\d+:", response, flags=re.IGNORECASE)

    for section in clip_sections[1:]:  # Skip text before first CLIP
        try:
            clip = _parse_single_clip(section)
            if clip:
                clips.append(clip)
        except Exception:
            continue

    return clips


def _parse_single_clip(section: str) -> ClipCandidate | None:
    """Parse a single clip section."""
    lines = section.strip().split("\n")

    start = None
    end = None
    hook = ""
    score = 5
    caption = ""
    reason = ""

    for line in lines:
        line = line.strip().lstrip("-").strip()
        lower = line.lower()

        if lower.startswith("start:"):
            start = _parse_timestamp(line.split(":", 1)[1].strip())
        elif lower.startswith("end:"):
            end = _parse_timestamp(line.split(":", 1)[1].strip())
        elif lower.startswith("hook:"):
            hook = line.split(":", 1)[1].strip().strip('"')
        elif lower.startswith("score:"):
            score_match = re.search(r"(\d+)", line)
            if score_match:
                score = int(score_match.group(1))
        elif lower.startswith("caption:"):
            caption = line.split(":", 1)[1].strip()
        elif lower.startswith("why viral:") or lower.startswith("reason:"):
            reason = line.split(":", 1)[1].strip()

    if start is not None and end is not None and end > start:
        return ClipCandidate(
            start=start,
            end=end,
            duration=end - start,
            hook=hook,
            score=score,
            caption=caption,
            reason=reason,
        )
    return None


def _parse_timestamp(ts: str) -> float | None:
    """Parse MM:SS or HH:MM:SS timestamp to seconds."""
    ts = ts.strip()
    parts = ts.split(":")

    try:
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    except ValueError:
        pass
    return None


def extract_clips(
    video_path: Path,
    clips: list[ClipCandidate],
    output_dir: Path,
    transcript: Transcript | None = None,
    vertical: bool = True,
) -> list[GeneratedClip]:
    """Extract clip segments from video.

    Args:
        video_path: Source video path.
        clips: Clip candidates to extract.
        output_dir: Directory for output clips.
        transcript: Original transcript for clip text.
        vertical: Convert to vertical 9:16 format.

    Returns:
        List of generated clip files.
    """
    logger = get_logger()
    output_dir.mkdir(parents=True, exist_ok=True)

    generated = []

    for i, clip in enumerate(clips, 1):
        logger.info(f"Extracting clip {i}/{len(clips)}: {clip.duration:.1f}s @ {clip.start:.1f}s")

        # Generate output filename
        output_path = output_dir / f"clip_{i:02d}_{int(clip.start)}s.mp4"

        # Get clip transcript
        clip_text = _get_clip_transcript(transcript, clip.start, clip.end) if transcript else ""

        # Build FFmpeg command
        if vertical:
            # Convert to 9:16 with center crop
            vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
        else:
            vf = None

        args = [
            "-ss", str(clip.start),
            "-i", str(video_path),
            "-t", str(clip.duration),
        ]

        if vf:
            args.extend(["-vf", vf])

        args.extend([
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            str(output_path),
        ])

        run_ffmpeg(args)

        # Generate metadata for clip
        if clip_text:
            metadata_response = generate_clip_metadata(clip_text)
            title, caption, hashtags = _parse_clip_metadata(metadata_response)
        else:
            title = clip.hook[:40] if clip.hook else f"Clip {i}"
            caption = clip.caption
            hashtags = []

        generated.append(GeneratedClip(
            path=output_path,
            start=clip.start,
            end=clip.end,
            title=title,
            caption=caption or clip.caption,
            hashtags=hashtags,
            transcript=clip_text,
        ))

        logger.info(f"  → {output_path.name}")

    logger.info(f"Extracted {len(generated)} clips to {output_dir}")
    return generated


def _get_clip_transcript(
    transcript: Transcript,
    start: float,
    end: float,
) -> str:
    """Get transcript text for a time range."""
    texts = []
    for seg in transcript.segments:
        # Include segment if it overlaps with clip range
        if seg.end > start and seg.start < end:
            texts.append(seg.text)
    return " ".join(texts)


def _parse_clip_metadata(response: str) -> tuple[str, str, list[str]]:
    """Parse clip metadata response."""
    title = ""
    caption = ""
    hashtags = []

    for line in response.split("\n"):
        line = line.strip()
        lower = line.lower()

        if lower.startswith("title:"):
            title = line.split(":", 1)[1].strip()
        elif lower.startswith("caption:"):
            caption = line.split(":", 1)[1].strip()
        elif lower.startswith("hashtags:"):
            tags_str = line.split(":", 1)[1].strip()
            hashtags = [t.strip() for t in re.findall(r"#\w+", tags_str)]

    return title, caption, hashtags


def save_clips_manifest(
    clips: list[GeneratedClip],
    output_path: Path,
) -> Path:
    """Save clips manifest as JSON.

    Args:
        clips: Generated clips.
        output_path: Output JSON path.

    Returns:
        Path to manifest file.
    """
    data = {
        "clips": [
            {
                "file": clip.path.name,
                "start": clip.start,
                "end": clip.end,
                "duration": clip.end - clip.start,
                "title": clip.title,
                "caption": clip.caption,
                "hashtags": clip.hashtags,
                "transcript": clip.transcript,
            }
            for clip in clips
        ]
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return output_path
