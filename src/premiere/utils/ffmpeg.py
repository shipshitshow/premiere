"""FFmpeg wrapper utilities."""

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from premiere.utils.logger import get_logger


@dataclass
class VideoInfo:
    """Video file metadata."""

    path: Path
    duration: float
    width: int
    height: int
    fps: float
    video_codec: str
    audio_codec: str | None
    audio_sample_rate: int | None
    audio_channels: int | None
    file_size: int
    bitrate: int


class FFmpegError(Exception):
    """FFmpeg execution error."""


def check_ffmpeg() -> bool:
    """Check if FFmpeg is installed and accessible.

    Returns:
        True if FFmpeg is available.

    Raises:
        FFmpegError: If FFmpeg is not found.
    """
    if shutil.which("ffmpeg") is None:
        raise FFmpegError(
            "FFmpeg not found. Install it with: brew install ffmpeg"
        )
    if shutil.which("ffprobe") is None:
        raise FFmpegError(
            "ffprobe not found. Install FFmpeg with: brew install ffmpeg"
        )
    return True


def probe(video_path: Path) -> VideoInfo:
    """Get video file metadata using ffprobe.

    Args:
        video_path: Path to video file.

    Returns:
        VideoInfo with file metadata.

    Raises:
        FFmpegError: If probe fails.
    """
    check_ffmpeg()
    logger = get_logger()

    if not video_path.exists():
        raise FFmpegError(f"Video file not found: {video_path}")

    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(video_path),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        raise FFmpegError(f"ffprobe failed: {e.stderr}") from e
    except json.JSONDecodeError as e:
        raise FFmpegError(f"Failed to parse ffprobe output: {e}") from e

    # Find video stream
    video_stream = next(
        (s for s in data.get("streams", []) if s.get("codec_type") == "video"),
        None,
    )
    if not video_stream:
        raise FFmpegError(f"No video stream found in {video_path}")

    # Find audio stream
    audio_stream = next(
        (s for s in data.get("streams", []) if s.get("codec_type") == "audio"),
        None,
    )

    # Parse frame rate
    fps_str = video_stream.get("r_frame_rate", "30/1")
    if "/" in fps_str:
        num, den = fps_str.split("/")
        fps = float(num) / float(den) if float(den) != 0 else 30.0
    else:
        fps = float(fps_str)

    format_info = data.get("format", {})

    return VideoInfo(
        path=video_path,
        duration=float(format_info.get("duration", 0)),
        width=int(video_stream.get("width", 0)),
        height=int(video_stream.get("height", 0)),
        fps=fps,
        video_codec=video_stream.get("codec_name", "unknown"),
        audio_codec=audio_stream.get("codec_name") if audio_stream else None,
        audio_sample_rate=int(audio_stream.get("sample_rate", 0)) if audio_stream else None,
        audio_channels=int(audio_stream.get("channels", 0)) if audio_stream else None,
        file_size=int(format_info.get("size", 0)),
        bitrate=int(format_info.get("bit_rate", 0)),
    )


def run_ffmpeg(
    args: list[str],
    progress_callback: callable | None = None,
) -> subprocess.CompletedProcess:
    """Run FFmpeg with given arguments.

    Args:
        args: FFmpeg command arguments (without 'ffmpeg' prefix).
        progress_callback: Optional callback for progress updates.

    Returns:
        Completed process result.

    Raises:
        FFmpegError: If FFmpeg fails.
    """
    check_ffmpeg()
    logger = get_logger()

    cmd = ["ffmpeg", "-y", "-hide_banner"] + args
    logger.debug(f"Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        return result
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg failed: {e.stderr}")
        raise FFmpegError(f"FFmpeg failed: {e.stderr}") from e


def extract_audio(video_path: Path, output_path: Path) -> Path:
    """Extract audio from video file.

    Args:
        video_path: Path to video file.
        output_path: Path for output audio file.

    Returns:
        Path to extracted audio file.
    """
    run_ffmpeg([
        "-i", str(video_path),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "48000",
        "-ac", "2",
        str(output_path),
    ])
    return output_path


def get_resolution_dimensions(resolution: str) -> tuple[int, int]:
    """Convert resolution string to width/height.

    Args:
        resolution: Resolution string (720p, 1080p, 4k).

    Returns:
        Tuple of (width, height).
    """
    resolutions = {
        "720p": (1280, 720),
        "1080p": (1920, 1080),
        "1440p": (2560, 1440),
        "4k": (3840, 2160),
        "2160p": (3840, 2160),
    }
    return resolutions.get(resolution.lower(), (1920, 1080))
