"""Configuration management for Premiere."""

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigValidationError(Exception):
    """Configuration validation error."""


class SilenceConfig(BaseModel):
    """Silence detection configuration."""

    threshold_db: float = Field(default=-40, ge=-80, le=0)
    min_duration: float = Field(default=0.5, gt=0, le=10)
    padding: float = Field(default=0.1, ge=0, le=5)

    @field_validator("threshold_db")
    @classmethod
    def validate_threshold(cls, v: float) -> float:
        """Validate silence threshold is in reasonable range."""
        if v > 0:
            raise ValueError("threshold_db must be negative (in dB)")
        return v


class VideoConfig(BaseModel):
    """Video processing configuration."""

    target_resolution: str = "1080p"
    target_fps: int = Field(default=30, ge=1, le=120)
    stabilization: bool = True
    stabilization_strength: float = Field(default=0.5, ge=0, le=1)
    color_correction: bool = True

    @field_validator("target_resolution")
    @classmethod
    def validate_resolution(cls, v: str) -> str:
        """Validate resolution is a known value."""
        valid_resolutions = {"720p", "1080p", "1440p", "4k", "2160p"}
        if v.lower() not in valid_resolutions:
            raise ValueError(f"Invalid resolution: {v}. Valid options: {valid_resolutions}")
        return v


class AudioConfig(BaseModel):
    """Audio enhancement configuration."""

    target_lufs: float = Field(default=-14, ge=-30, le=-5)
    noise_reduction: bool = True
    noise_reduction_strength: float = Field(default=0.5, ge=0, le=1)
    normalize: bool = True
    compression: bool = True
    de_ess: bool = True
    eq_voice: bool = True


class MusicConfig(BaseModel):
    """Background music configuration."""

    enabled: bool = False
    genre: str = "ambient"
    volume_db: float = Field(default=-20, ge=-40, le=0)
    auto_duck: bool = True
    fade_in: float = Field(default=2.0, ge=0, le=30)
    fade_out: float = Field(default=3.0, ge=0, le=30)


class AIConfig(BaseModel):
    """AI configuration."""

    provider: Literal["anthropic", "openai"] = "anthropic"
    model: str = "claude-sonnet-4-20250514"
    transcription_model: Literal["tiny", "base", "small", "medium", "large"] = "base"
    title_count: int = Field(default=5, ge=1, le=10)
    tone: Literal["professional", "casual", "clickbait"] = "professional"
    include_hashtags: bool = True
    include_chapters: bool = True


class ThumbnailConfig(BaseModel):
    """Thumbnail generation configuration."""

    width: int = Field(default=1280, ge=100, le=4096)
    height: int = Field(default=720, ge=100, le=4096)
    text_overlay: bool = True
    face_detection: bool = True
    style: Literal["bold", "minimal", "cinematic"] = "bold"


class YouTubeConfig(BaseModel):
    """YouTube upload configuration."""

    privacy: Literal["public", "private", "unlisted"] = "private"
    category: str = "22"
    notify_subscribers: bool = False
    made_for_kids: bool = False
    channel_id: str | None = None
    playlist_id: str | None = None


class ProcessingConfig(BaseModel):
    """Processing configuration."""

    temp_dir: Path | None = None
    keep_temp: bool = False
    gpu_acceleration: bool = True
    threads: int = Field(default=0, ge=0, le=64)


class OutputConfig(BaseModel):
    """Output configuration."""

    format: Literal["mp4", "mkv", "webm", "mov"] = "mp4"
    video_codec: Literal["libx264", "libx265", "vp9", "av1"] = "libx264"
    audio_codec: Literal["aac", "mp3", "opus", "flac"] = "aac"
    quality_preset: Literal["ultrafast", "fast", "medium", "slow", "veryslow"] = "medium"


class Config(BaseSettings):
    """Main configuration class."""

    model_config = SettingsConfigDict(
        env_prefix="PREMIERE_",
        env_nested_delimiter="__",
    )

    silence: SilenceConfig = Field(default_factory=SilenceConfig)
    video: VideoConfig = Field(default_factory=VideoConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)
    music: MusicConfig = Field(default_factory=MusicConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    thumbnail: ThumbnailConfig = Field(default_factory=ThumbnailConfig)
    youtube: YouTubeConfig = Field(default_factory=YouTubeConfig)
    processing: ProcessingConfig = Field(default_factory=ProcessingConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)

    # API keys from environment
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None


def load_config(config_path: Path | None = None) -> Config:
    """Load configuration from file and environment.

    Args:
        config_path: Path to YAML config file.

    Returns:
        Loaded configuration.
    """
    config_data: dict[str, Any] = {}

    # Load from default config
    default_config = Path(__file__).parent.parent.parent.parent / "config" / "default.yaml"
    if default_config.exists():
        with open(default_config) as f:
            config_data = yaml.safe_load(f) or {}

    # Override with custom config
    if config_path and config_path.exists():
        with open(config_path) as f:
            custom = yaml.safe_load(f) or {}
            _deep_merge(config_data, custom)

    return Config(**config_data)


def _deep_merge(base: dict, override: dict) -> None:
    """Deep merge override into base dict."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


# Global config instance
_config: Config | None = None


def get_config() -> Config:
    """Get the global config instance."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def set_config(config: Config) -> None:
    """Set the global config instance."""
    global _config
    _config = config


def get_temp_dir(output_dir: Path | None = None) -> Path:
    """Get temporary directory for processing.

    Uses output_dir/temp/ if provided, otherwise workspace/output/temp/.
    Falls back to system temp if not in project.

    Args:
        output_dir: Optional output directory (will use output_dir/temp/).

    Returns:
        Path to temporary directory (created if needed).
    """
    # Check if we're in the premiere project directory
    is_project = (
        (Path.cwd() / "pyproject.toml").exists()
        or (Path.cwd() / "src" / "premiere").exists()
    )

    if output_dir:
        # Use temp subdirectory within the provided output directory
        temp_dir = output_dir / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        return temp_dir
    elif is_project:
        # Use workspace/output/temp/ as default (reuse existing output folder)
        temp_dir = Path.cwd() / "output" / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        return temp_dir
    else:
        # Fallback to system temp
        import tempfile
        return Path(tempfile.gettempdir())


def validate_config(config: Config | None = None) -> list[str]:
    """Validate configuration and return any warnings.

    Args:
        config: Configuration to validate (uses global if None).

    Returns:
        List of warning messages (empty if all valid).

    Raises:
        ConfigValidationError: If configuration has critical errors.
    """
    import shutil

    warnings = []
    cfg = config or get_config()

    # Check FFmpeg availability
    if shutil.which("ffmpeg") is None:
        raise ConfigValidationError(
            "FFmpeg not found. Please install FFmpeg to use Premiere. "
            "Install with: brew install ffmpeg (macOS) or apt install ffmpeg (Linux)"
        )

    if shutil.which("ffprobe") is None:
        raise ConfigValidationError(
            "ffprobe not found. Please install FFmpeg to use Premiere."
        )

    # Validate thumbnail dimensions maintain reasonable aspect ratio
    aspect_ratio = cfg.thumbnail.width / cfg.thumbnail.height
    if aspect_ratio < 0.5 or aspect_ratio > 3:
        warnings.append(
            f"Unusual thumbnail aspect ratio ({aspect_ratio:.2f}). "
            "YouTube recommends 16:9 (1.78) for thumbnails."
        )

    # Check for API keys if using AI features
    if cfg.ai.provider == "anthropic" and not cfg.anthropic_api_key:
        warnings.append(
            "ANTHROPIC_API_KEY not set. Claude CLI will be used for AI features. "
            "Set PREMIERE_ANTHROPIC_API_KEY environment variable to use API directly."
        )
    elif cfg.ai.provider == "openai" and not cfg.openai_api_key:
        warnings.append(
            "OPENAI_API_KEY not set. Set PREMIERE_OPENAI_API_KEY environment variable."
        )

    # Validate audio LUFS target
    if cfg.audio.target_lufs > -10:
        warnings.append(
            f"Target LUFS ({cfg.audio.target_lufs}) is very high. "
            "YouTube recommends -14 LUFS for optimal playback."
        )

    # Validate video settings
    if cfg.video.target_fps > 60:
        warnings.append(
            f"Target FPS ({cfg.video.target_fps}) is high. "
            "Most platforms support up to 60 FPS."
        )

    return warnings


def validate_config_on_startup() -> None:
    """Validate configuration on application startup.

    Logs warnings and raises errors for critical issues.
    """
    from premiere.utils.logger import get_logger

    logger = get_logger()

    try:
        warnings = validate_config()
        for warning in warnings:
            logger.warning(f"Config warning: {warning}")
    except ConfigValidationError as e:
        logger.error(f"Configuration error: {e}")
        raise
