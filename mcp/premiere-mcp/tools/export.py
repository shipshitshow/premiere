"""Export tools for MCP server."""

from pathlib import Path


async def export_video(
    path: str,
    output: str,
    format: str = "mp4",
    resolution: str | None = None,
    quality: str = "high",
) -> dict:
    """Export video with specified settings.

    Args:
        path: Path to input video.
        output: Output path.
        format: Output format (mp4, mov, webm).
        resolution: Target resolution (1080p, 720p, 480p, or WxH).
        quality: Quality preset (high, medium, low).

    Returns:
        Dict with output_path and file_size.
    """
    from premiere.utils.ffmpeg import run_ffmpeg

    video_path = Path(path)
    output_path = Path(output)

    # Build FFmpeg command
    cmd = ["-i", str(video_path)]

    # Resolution scaling
    if resolution:
        if resolution == "1080p":
            cmd.extend(["-vf", "scale=-1:1080"])
        elif resolution == "720p":
            cmd.extend(["-vf", "scale=-1:720"])
        elif resolution == "480p":
            cmd.extend(["-vf", "scale=-1:480"])
        elif "x" in resolution:
            w, h = resolution.split("x")
            cmd.extend(["-vf", f"scale={w}:{h}"])

    # Quality presets
    quality_map = {
        "high": {"crf": "18", "preset": "slow"},
        "medium": {"crf": "23", "preset": "medium"},
        "low": {"crf": "28", "preset": "fast"},
    }
    q = quality_map.get(quality, quality_map["medium"])
    cmd.extend(["-crf", q["crf"], "-preset", q["preset"]])

    # Output format settings
    if format == "mp4":
        cmd.extend(["-c:v", "libx264", "-c:a", "aac"])
    elif format == "webm":
        cmd.extend(["-c:v", "libvpx-vp9", "-c:a", "libopus"])
    elif format == "mov":
        cmd.extend(["-c:v", "libx264", "-c:a", "aac", "-f", "mov"])

    cmd.append(str(output_path))
    run_ffmpeg(cmd)

    return {
        "output_path": str(output_path),
        "file_size_mb": round(output_path.stat().st_size / 1024 / 1024, 2),
    }


async def export_clips(
    video_path: str,
    clips: list[dict],
    output_dir: str,
    vertical: bool = True,
    with_captions: bool = False,
) -> dict:
    """Export multiple clips from video.

    Args:
        video_path: Path to source video.
        clips: List of clip definitions with start and end times.
               Each clip: {"start": float, "end": float, "name": str (optional)}
        output_dir: Directory to save clips.
        vertical: Convert to vertical 9:16 format.
        with_captions: Add burned-in captions.

    Returns:
        Dict with exported clips array and output_dir.
    """
    from premiere.utils.ffmpeg import run_ffmpeg

    video = Path(video_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    exported = []

    for i, clip in enumerate(clips):
        name = clip.get("name", f"clip_{i+1:02d}")
        start = clip["start"]
        end = clip["end"]
        duration = end - start

        output_file = out_dir / f"{name}.mp4"

        cmd = [
            "-i", str(video),
            "-ss", str(start),
            "-t", str(duration),
        ]

        # Vertical crop for shorts
        if vertical:
            cmd.extend(["-vf", "crop=ih*9/16:ih,scale=1080:1920"])

        cmd.extend([
            "-c:v", "libx264",
            "-preset", "fast",
            "-c:a", "aac",
            "-b:a", "192k",
            str(output_file),
        ])

        run_ffmpeg(cmd)

        exported.append({
            "path": str(output_file),
            "name": name,
            "start": start,
            "end": end,
            "duration": duration,
            "file_size_mb": round(output_file.stat().st_size / 1024 / 1024, 2),
        })

    return {
        "output_dir": str(out_dir),
        "clips_count": len(exported),
        "clips": exported,
    }
