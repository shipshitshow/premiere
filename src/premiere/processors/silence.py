"""Silence detection and removal processor."""

import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from premiere.utils.config import SilenceConfig, get_config
from premiere.utils.ffmpeg import FFmpegError, check_ffmpeg, run_ffmpeg
from premiere.utils.logger import get_logger


@dataclass
class SilenceSegment:
    """Represents a detected silence segment."""

    start: float
    end: float
    duration: float


@dataclass
class AudioSegment:
    """Represents a segment of audio to keep."""

    start: float
    end: float


def detect_silence(
    video_path: Path,
    threshold_db: float | None = None,
    min_duration: float | None = None,
) -> list[SilenceSegment]:
    """Detect silence segments in video audio.

    Args:
        video_path: Path to video file.
        threshold_db: Silence threshold in dB (default from config).
        min_duration: Minimum silence duration in seconds (default from config).

    Returns:
        List of detected silence segments.
    """
    check_ffmpeg()
    logger = get_logger()
    config = get_config().silence

    threshold = threshold_db if threshold_db is not None else config.threshold_db
    duration = min_duration if min_duration is not None else config.min_duration

    logger.info(f"Detecting silence in {video_path.name} (threshold: {threshold}dB, min: {duration}s)")

    # Use silencedetect filter
    cmd = [
        "ffmpeg",
        "-i", str(video_path),
        "-af", f"silencedetect=noise={threshold}dB:d={duration}",
        "-f", "null",
        "-",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        output = result.stderr
    except subprocess.CalledProcessError as e:
        raise FFmpegError(f"Silence detection failed: {e.stderr}") from e

    # Parse silence segments
    segments = []
    silence_start = None

    for line in output.split("\n"):
        # Match silence_start
        start_match = re.search(r"silence_start: ([\d.]+)", line)
        if start_match:
            silence_start = float(start_match.group(1))

        # Match silence_end
        end_match = re.search(r"silence_end: ([\d.]+) \| silence_duration: ([\d.]+)", line)
        if end_match and silence_start is not None:
            silence_end = float(end_match.group(1))
            silence_duration = float(end_match.group(2))
            segments.append(SilenceSegment(
                start=silence_start,
                end=silence_end,
                duration=silence_duration,
            ))
            silence_start = None

    logger.info(f"Found {len(segments)} silence segments")
    return segments


def get_audio_segments(
    silence_segments: list[SilenceSegment],
    video_duration: float,
    padding: float | None = None,
) -> list[AudioSegment]:
    """Convert silence segments to audio segments to keep.

    Args:
        silence_segments: List of detected silence segments.
        video_duration: Total video duration.
        padding: Padding around cuts in seconds (default from config).

    Returns:
        List of audio segments to keep.
    """
    config = get_config().silence
    pad = padding if padding is not None else config.padding

    if not silence_segments:
        return [AudioSegment(start=0, end=video_duration)]

    segments = []
    current_pos = 0.0

    for silence in silence_segments:
        # Add segment before silence (with padding)
        segment_end = min(silence.start + pad, video_duration)
        if segment_end > current_pos:
            segments.append(AudioSegment(start=current_pos, end=segment_end))

        # Move position to after silence (with padding)
        current_pos = max(silence.end - pad, current_pos)

    # Add final segment
    if current_pos < video_duration:
        segments.append(AudioSegment(start=current_pos, end=video_duration))

    return segments


def cut_silence(
    video_path: Path,
    output_path: Path,
    threshold_db: float | None = None,
    min_duration: float | None = None,
    padding: float | None = None,
) -> Path:
    """Remove silence from video.

    Args:
        video_path: Path to input video.
        output_path: Path for output video.
        threshold_db: Silence threshold in dB.
        min_duration: Minimum silence duration in seconds.
        padding: Padding around cuts in seconds.

    Returns:
        Path to output video with silence removed.
    """
    logger = get_logger()

    # Detect silence
    silence_segments = detect_silence(video_path, threshold_db, min_duration)

    if not silence_segments:
        logger.info("No silence detected, copying original file")
        run_ffmpeg(["-i", str(video_path), "-c", "copy", str(output_path)])
        return output_path

    # Get video duration
    from premiere.utils.ffmpeg import probe
    info = probe(video_path)

    # Get segments to keep
    audio_segments = get_audio_segments(silence_segments, info.duration, padding)
    logger.info(f"Keeping {len(audio_segments)} segments")

    if not audio_segments:
        raise FFmpegError("No audio segments to keep - video would be empty")

    # Create filter complex for concatenation
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        segment_files = []

        # Extract each segment
        for i, segment in enumerate(audio_segments):
            segment_file = temp_path / f"segment_{i:04d}.mp4"
            duration = segment.end - segment.start

            run_ffmpeg([
                "-i", str(video_path),
                "-ss", str(segment.start),
                "-t", str(duration),
                "-c:v", "libx264",
                "-preset", "fast",
                "-c:a", "aac",
                "-b:a", "192k",
                str(segment_file),
            ])
            segment_files.append(segment_file)

        # Create concat file
        concat_file = temp_path / "concat.txt"
        with open(concat_file, "w") as f:
            for segment_file in segment_files:
                f.write(f"file '{segment_file}'\n")

        # Concatenate segments
        run_ffmpeg([
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c", "copy",
            str(output_path),
        ])

    logger.info(f"Silence removed, output: {output_path}")
    return output_path
