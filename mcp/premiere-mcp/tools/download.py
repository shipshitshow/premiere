"""Download tools for MCP server."""

from pathlib import Path


async def download_video(
    url: str,
    output_dir: str | None = None,
    quality: str = "best",
) -> dict:
    """Download video from YouTube or other supported platforms.

    Args:
        url: Video URL (YouTube, Vimeo, etc.)
        output_dir: Directory to save video (default: current directory)
        quality: Video quality (best, 1080, 720, 480)

    Returns:
        Dict with path, title, duration, and metadata.
    """
    from premiere.downloaders.youtube_dl import download_video as dl_video, get_video_info

    output_path = Path(output_dir) if output_dir else Path.cwd()

    # Get video info first
    info = get_video_info(url)

    # Download
    video_path = dl_video(url, output_path, quality=quality)

    return {
        "path": str(video_path),
        "title": info.title,
        "channel": info.channel,
        "duration": info.duration,
        "duration_formatted": f"{info.duration // 60}:{info.duration % 60:02d}",
    }
