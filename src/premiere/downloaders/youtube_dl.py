"""YouTube video downloader using yt-dlp."""

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from premiere.utils.logger import get_logger


@dataclass
class VideoInfo:
    """YouTube video information."""

    id: str
    title: str
    description: str
    duration: int
    channel: str
    upload_date: str
    thumbnail_url: str
    view_count: int
    url: str


class DownloadError(Exception):
    """Download error."""


def check_ytdlp() -> bool:
    """Check if yt-dlp is installed.

    Returns:
        True if available.

    Raises:
        DownloadError: If not found.
    """
    if shutil.which("yt-dlp") is None:
        raise DownloadError(
            "yt-dlp not found. Install with: brew install yt-dlp"
        )
    return True


def get_video_info(url: str) -> VideoInfo:
    """Get video information without downloading.

    Args:
        url: YouTube video URL.

    Returns:
        VideoInfo with metadata.
    """
    import json

    check_ytdlp()
    logger = get_logger()

    logger.info(f"Fetching video info: {url}")

    cmd = [
        "yt-dlp",
        "--dump-json",
        "--no-download",
        url,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        raise DownloadError(f"Failed to get video info: {e.stderr}") from e

    return VideoInfo(
        id=data.get("id", ""),
        title=data.get("title", ""),
        description=data.get("description", ""),
        duration=data.get("duration", 0),
        channel=data.get("channel", data.get("uploader", "")),
        upload_date=data.get("upload_date", ""),
        thumbnail_url=data.get("thumbnail", ""),
        view_count=data.get("view_count", 0),
        url=url,
    )


def download_video(
    url: str,
    output_dir: Path,
    filename: str | None = None,
    quality: str = "best",
    audio_only: bool = False,
) -> Path:
    """Download video from YouTube.

    Args:
        url: YouTube video URL.
        output_dir: Directory for downloaded file.
        filename: Output filename (without extension).
        quality: Quality setting (best, 1080, 720, 480).
        audio_only: Download audio only.

    Returns:
        Path to downloaded file.
    """
    check_ytdlp()
    logger = get_logger()

    output_dir.mkdir(parents=True, exist_ok=True)

    # Build output template
    if filename:
        output_template = str(output_dir / f"{filename}.%(ext)s")
    else:
        output_template = str(output_dir / "%(title)s.%(ext)s")

    # Build format selector
    if audio_only:
        format_selector = "bestaudio[ext=m4a]/bestaudio"
    elif quality == "best":
        format_selector = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
    else:
        format_selector = f"bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/best[height<={quality}][ext=mp4]/best"

    cmd = [
        "yt-dlp",
        "-f", format_selector,
        "-o", output_template,
        "--merge-output-format", "mp4",
        "--no-playlist",
        "--progress",
        url,
    ]

    logger.info(f"Downloading: {url}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        raise DownloadError(f"Download failed: {e.stderr}") from e

    # Find downloaded file
    for line in result.stdout.split("\n"):
        if "[Merger]" in line or "[download]" in line:
            if "Destination:" in line:
                path_str = line.split("Destination:")[-1].strip()
                path = Path(path_str)
                if path.exists():
                    logger.info(f"Downloaded: {path}")
                    return path

    # Fallback: find most recent mp4 in output_dir
    mp4_files = sorted(output_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    if mp4_files:
        logger.info(f"Downloaded: {mp4_files[0]}")
        return mp4_files[0]

    raise DownloadError("Could not find downloaded file")


def download_thumbnail(url: str, output_path: Path) -> Path:
    """Download video thumbnail.

    Args:
        url: YouTube video URL.
        output_path: Output file path.

    Returns:
        Path to downloaded thumbnail.
    """
    check_ytdlp()
    logger = get_logger()

    cmd = [
        "yt-dlp",
        "--write-thumbnail",
        "--skip-download",
        "--convert-thumbnails", "jpg",
        "-o", str(output_path.with_suffix("")),
        url,
    ]

    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        raise DownloadError(f"Thumbnail download failed: {e.stderr}") from e

    # Find thumbnail file
    for ext in [".jpg", ".webp", ".png"]:
        thumb = output_path.with_suffix(ext)
        if thumb.exists():
            logger.info(f"Downloaded thumbnail: {thumb}")
            return thumb

    raise DownloadError("Could not find downloaded thumbnail")
