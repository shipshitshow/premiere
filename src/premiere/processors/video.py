"""Video cleanup and enhancement processor."""

import tempfile
from pathlib import Path

from premiere.utils.config import VideoConfig, get_config
from premiere.utils.ffmpeg import get_resolution_dimensions, probe, run_ffmpeg
from premiere.utils.logger import get_logger


def enhance_video(
    video_path: Path,
    output_path: Path,
    config: VideoConfig | None = None,
) -> Path:
    """Enhance video quality.

    Args:
        video_path: Path to input video.
        output_path: Path for output video.
        config: Video configuration (default from global config).

    Returns:
        Path to output video with enhancements.
    """
    logger = get_logger()
    cfg = config or get_config().video

    logger.info(f"Enhancing video: {video_path.name}")

    # Get video info
    info = probe(video_path)

    # Build video filter chain
    filters = []

    # Resolution scaling
    target_w, target_h = get_resolution_dimensions(cfg.target_resolution)
    if info.width != target_w or info.height != target_h:
        # Scale maintaining aspect ratio
        filters.append(f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease")
        filters.append(f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2")
        logger.info(f"Scaling from {info.width}x{info.height} to {target_w}x{target_h}")

    # Frame rate conversion
    if abs(info.fps - cfg.target_fps) > 0.5:
        filters.append(f"fps={cfg.target_fps}")
        logger.info(f"Converting frame rate from {info.fps:.2f} to {cfg.target_fps}")

    # Color correction
    if cfg.color_correction:
        # Auto color and levels normalization
        filters.append("colorlevels=rimax=0.902:gimax=0.902:bimax=0.902")
        filters.append("eq=saturation=1.1:contrast=1.05")

    # Stabilization is a two-pass process
    if cfg.stabilization:
        return _stabilize_video(video_path, output_path, filters, cfg)

    if not filters:
        logger.info("No video filters enabled, copying original")
        run_ffmpeg(["-i", str(video_path), "-c", "copy", str(output_path)])
        return output_path

    # Combine filters
    filter_chain = ",".join(filters)
    logger.debug(f"Video filter chain: {filter_chain}")

    # Run FFmpeg with video filters
    run_ffmpeg([
        "-i", str(video_path),
        "-vf", filter_chain,
        "-c:v", "libx264",
        "-preset", get_config().output.quality_preset,
        "-crf", "18",
        "-c:a", "copy",
        str(output_path),
    ])

    logger.info(f"Video enhanced, output: {output_path}")
    return output_path


def _stabilize_video(
    video_path: Path,
    output_path: Path,
    existing_filters: list[str],
    config: VideoConfig,
) -> Path:
    """Apply video stabilization (two-pass process).

    Args:
        video_path: Path to input video.
        output_path: Path for output video.
        existing_filters: Other filters to apply.
        config: Video configuration.

    Returns:
        Path to stabilized video.
    """
    logger = get_logger()
    logger.info("Applying video stabilization (two-pass)")

    smoothing = int(config.stabilization_strength * 30) + 10  # 10-40 range

    with tempfile.TemporaryDirectory() as temp_dir:
        transforms_file = Path(temp_dir) / "transforms.trf"

        # Pass 1: Analyze motion
        logger.info("Stabilization pass 1: Analyzing motion...")
        run_ffmpeg([
            "-i", str(video_path),
            "-vf", f"vidstabdetect=stepsize=6:shakiness=8:accuracy=9:result={transforms_file}",
            "-f", "null",
            "-",
        ])

        # Pass 2: Apply stabilization
        logger.info("Stabilization pass 2: Applying transform...")
        stab_filter = f"vidstabtransform=input={transforms_file}:smoothing={smoothing}:zoom=1"

        all_filters = [stab_filter] + existing_filters
        filter_chain = ",".join(all_filters)

        run_ffmpeg([
            "-i", str(video_path),
            "-vf", filter_chain,
            "-c:v", "libx264",
            "-preset", get_config().output.quality_preset,
            "-crf", "18",
            "-c:a", "copy",
            str(output_path),
        ])

    logger.info(f"Video stabilized, output: {output_path}")
    return output_path


def extract_keyframes(video_path: Path, output_dir: Path, count: int = 10) -> list[Path]:
    """Extract key frames from video for thumbnail candidates.

    Args:
        video_path: Path to video file.
        output_dir: Directory for output frames.
        count: Number of frames to extract.

    Returns:
        List of paths to extracted frames.
    """
    logger = get_logger()
    logger.info(f"Extracting {count} keyframes from {video_path.name}")

    output_dir.mkdir(parents=True, exist_ok=True)

    # Get video duration
    info = probe(video_path)
    interval = info.duration / (count + 1)

    frames = []
    for i in range(1, count + 1):
        timestamp = interval * i
        output_file = output_dir / f"frame_{i:03d}.jpg"

        run_ffmpeg([
            "-ss", str(timestamp),
            "-i", str(video_path),
            "-vframes", "1",
            "-q:v", "2",
            str(output_file),
        ])

        if output_file.exists():
            frames.append(output_file)

    logger.info(f"Extracted {len(frames)} keyframes")
    return frames
