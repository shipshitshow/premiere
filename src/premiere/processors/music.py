"""Background music processor with auto-ducking."""

import random
from pathlib import Path

from premiere.utils.config import MusicConfig, get_config
from premiere.utils.ffmpeg import probe, run_ffmpeg
from premiere.utils.logger import get_logger


# Music library directory (relative to project root)
MUSIC_DIR = Path(__file__).parent.parent.parent.parent / "music"


def get_available_tracks(genre: str | None = None) -> list[Path]:
    """Get available music tracks from library.

    Args:
        genre: Optional genre filter (matches directory or filename).

    Returns:
        List of available music file paths.
    """
    if not MUSIC_DIR.exists():
        return []

    tracks = []
    for ext in ["*.mp3", "*.wav", "*.m4a", "*.aac"]:
        for track in MUSIC_DIR.rglob(ext):
            if genre is None or genre.lower() in track.stem.lower():
                tracks.append(track)

    return tracks


def select_track(genre: str | None = None, duration: float | None = None) -> Path | None:
    """Select a suitable music track.

    Args:
        genre: Preferred genre/mood.
        duration: Video duration to match (selects track >= duration).

    Returns:
        Path to selected track or None if no suitable track.
    """
    logger = get_logger()

    tracks = get_available_tracks(genre)
    if not tracks:
        logger.warning(f"No music tracks found in {MUSIC_DIR}")
        return None

    # Filter by duration if specified
    if duration is not None:
        suitable = []
        for track in tracks:
            try:
                info = probe(track)
                if info.duration >= duration:
                    suitable.append(track)
            except Exception:
                continue
        if suitable:
            tracks = suitable

    # Random selection
    selected = random.choice(tracks)
    logger.info(f"Selected music track: {selected.name}")
    return selected


def add_background_music(
    video_path: Path,
    output_path: Path,
    music_path: Path | None = None,
    config: MusicConfig | None = None,
) -> Path:
    """Add background music with auto-ducking.

    Args:
        video_path: Path to input video.
        output_path: Path for output video.
        music_path: Path to music file (auto-selected if None).
        config: Music configuration (default from global config).

    Returns:
        Path to output video with background music.
    """
    logger = get_logger()
    cfg = config or get_config().music

    if not cfg.enabled:
        logger.info("Background music disabled, copying original")
        run_ffmpeg(["-i", str(video_path), "-c", "copy", str(output_path)])
        return output_path

    # Get video info
    video_info = probe(video_path)

    # Select music track
    if music_path is None:
        music_path = select_track(cfg.genre, video_info.duration)
        if music_path is None:
            logger.warning("No music track available, skipping")
            run_ffmpeg(["-i", str(video_path), "-c", "copy", str(output_path)])
            return output_path

    logger.info(f"Adding background music: {music_path.name}")

    # Build audio filter
    # [0:a] = original audio, [1:a] = music
    filters = []

    # Trim music to video length and add fades
    music_filter = f"[1:a]atrim=0:{video_info.duration}"
    music_filter += f",afade=t=in:st=0:d={cfg.fade_in}"
    music_filter += f",afade=t=out:st={video_info.duration - cfg.fade_out}:d={cfg.fade_out}"
    music_filter += f",volume={cfg.volume_db}dB"
    music_filter += "[music]"
    filters.append(music_filter)

    if cfg.auto_duck:
        # Sidechain compression - duck music when speech is present
        # Use compressor triggered by original audio
        filters.append(
            "[0:a]asplit=2[speech][sc];"
            "[sc]aformat=channel_layouts=mono[sc_mono];"
            "[music][sc_mono]sidechaincompress="
            "threshold=0.02:ratio=6:attack=50:release=300:level_sc=0.8"
            "[ducked];"
            "[speech][ducked]amix=inputs=2:duration=first:dropout_transition=2[out]"
        )
    else:
        # Simple mix without ducking
        filters.append("[0:a][music]amix=inputs=2:duration=first:dropout_transition=2[out]")

    filter_complex = ";".join(filters)

    run_ffmpeg([
        "-i", str(video_path),
        "-i", str(music_path),
        "-filter_complex", filter_complex,
        "-map", "0:v",
        "-map", "[out]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        str(output_path),
    ])

    logger.info(f"Background music added, output: {output_path}")
    return output_path
