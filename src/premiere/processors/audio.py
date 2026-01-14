"""Audio enhancement processor."""

from pathlib import Path

from premiere.utils.config import AudioConfig, get_config
from premiere.utils.ffmpeg import run_ffmpeg
from premiere.utils.logger import get_logger


def enhance_audio(
    video_path: Path,
    output_path: Path,
    config: AudioConfig | None = None,
) -> Path:
    """Enhance audio quality in video.

    Args:
        video_path: Path to input video.
        output_path: Path for output video.
        config: Audio configuration (default from global config).

    Returns:
        Path to output video with enhanced audio.
    """
    logger = get_logger()
    cfg = config or get_config().audio

    logger.info(f"Enhancing audio in {video_path.name}")

    # Build audio filter chain
    filters = []

    # Noise reduction
    if cfg.noise_reduction:
        # afftdn: FFT-based noise reduction
        nr_strength = int(cfg.noise_reduction_strength * 30)  # 0-30 range
        filters.append(f"afftdn=nf=-{nr_strength}")

    # De-essing
    if cfg.de_ess:
        # High frequency de-esser using multiband compression
        filters.append("deesser=i=0.4:m=0.5:f=0.5:s=o")

    # Voice EQ enhancement
    if cfg.eq_voice:
        # Boost clarity frequencies, cut mud
        filters.append("equalizer=f=100:t=h:w=100:g=-3")  # Cut mud
        filters.append("equalizer=f=3000:t=h:w=2000:g=2")  # Boost presence
        filters.append("equalizer=f=8000:t=h:w=3000:g=1")  # Air

    # Dynamic range compression
    if cfg.compression:
        # Light compression for consistent levels
        filters.append("acompressor=threshold=-20dB:ratio=3:attack=5:release=50")

    # Loudness normalization (EBU R128 / YouTube standard)
    if cfg.normalize:
        filters.append(
            f"loudnorm=I={cfg.target_lufs}:TP=-1.5:LRA=11:print_format=summary"
        )

    if not filters:
        logger.info("No audio filters enabled, copying original")
        run_ffmpeg(["-i", str(video_path), "-c", "copy", str(output_path)])
        return output_path

    # Combine filters
    filter_chain = ",".join(filters)
    logger.debug(f"Audio filter chain: {filter_chain}")

    # Run FFmpeg with audio filters
    run_ffmpeg([
        "-i", str(video_path),
        "-c:v", "copy",
        "-af", filter_chain,
        "-c:a", "aac",
        "-b:a", "192k",
        str(output_path),
    ])

    logger.info(f"Audio enhanced, output: {output_path}")
    return output_path


def measure_loudness(video_path: Path) -> dict:
    """Measure audio loudness using EBU R128.

    Args:
        video_path: Path to video file.

    Returns:
        Dict with loudness measurements.
    """
    import re
    import subprocess

    logger = get_logger()
    logger.info(f"Measuring loudness of {video_path.name}")

    cmd = [
        "ffmpeg",
        "-i", str(video_path),
        "-af", "loudnorm=print_format=json",
        "-f", "null",
        "-",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    # Parse loudness from stderr
    measurements = {
        "input_i": None,
        "input_tp": None,
        "input_lra": None,
        "input_thresh": None,
    }

    for line in result.stderr.split("\n"):
        for key in measurements:
            if f'"{key}"' in line:
                match = re.search(r'"' + key + r'"\s*:\s*"?([-\d.]+)', line)
                if match:
                    measurements[key] = float(match.group(1))

    logger.info(f"Loudness: {measurements.get('input_i', 'N/A')} LUFS")
    return measurements
