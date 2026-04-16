"""Analysis tools for MCP server."""

from pathlib import Path


async def get_video_info(path: str) -> dict:
    """Get video file information.

    Args:
        path: Path to video file.

    Returns:
        Dict with duration, resolution, fps, codecs, file size.
    """
    from premiere.utils.ffmpeg import probe

    video_path = Path(path)
    info = probe(video_path)

    return {
        "path": str(video_path),
        "duration": info.duration,
        "duration_formatted": f"{int(info.duration // 60)}:{int(info.duration % 60):02d}",
        "width": info.width,
        "height": info.height,
        "resolution": f"{info.width}x{info.height}",
        "fps": info.fps,
        "video_codec": info.video_codec,
        "audio_codec": info.audio_codec,
        "file_size_mb": round(info.file_size / 1024 / 1024, 2),
        "bitrate_kbps": round(info.bitrate / 1000),
    }


async def detect_segments(
    path: str,
    threshold_db: float = -40,
    min_duration: float = 0.5,
    padding: float = 0.1,
) -> dict:
    """Detect silence/speech segments in video.

    Args:
        path: Path to video file.
        threshold_db: Silence threshold in dB.
        min_duration: Minimum silence duration in seconds.
        padding: Padding around cuts in seconds.

    Returns:
        Dict with silence_segments, audio_segments, video_duration, and stats.
    """
    from premiere.processors.silence import get_segments

    video_path = Path(path)
    return get_segments(video_path, threshold_db, min_duration, padding)


async def detect_viral_moments(
    path: str,
    max_clips: int = 5,
    min_duration: int = 15,
    max_duration: int = 60,
) -> dict:
    """Detect viral moments in video using AI.

    Args:
        path: Path to video file.
        max_clips: Maximum number of clips to detect.
        min_duration: Minimum clip duration in seconds.
        max_duration: Maximum clip duration in seconds.

    Returns:
        Dict with clips array containing start, end, score, hook, and reason.
    """
    from premiere.generators.clips import detect_viral_moments as detect
    from premiere.generators.transcription import transcribe_video
    from premiere.utils.ffmpeg import probe

    video_path = Path(path)

    # Get video info
    info = probe(video_path)

    # Transcribe
    transcript = transcribe_video(video_path)

    # Detect viral moments
    candidates = detect(
        transcript,
        info.duration,
        max_clips=max_clips,
        min_duration=min_duration,
        max_duration=max_duration,
    )

    return {
        "clips": [
            {
                "start": c.start,
                "end": c.end,
                "duration": c.end - c.start,
                "score": c.score,
                "hook": c.hook,
                "reason": c.reason,
            }
            for c in candidates
        ],
        "total_found": len(candidates),
    }
