"""Configuration management for Premiere."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SilenceConfig(BaseModel):
    """Silence detection configuration."""

    threshold_db: float = -40
    min_duration: float = 0.5
    padding: float = 0.1


class VideoConfig(BaseModel):
    """Video processing configuration."""

    target_resolution: str = "1080p"
    target_fps: int = 30
    stabilization: bool = True
    stabilization_strength: float = 0.5
    color_correction: bool = True


class AudioConfig(BaseModel):
    """Audio enhancement configuration."""

    target_lufs: float = -14
    noise_reduction: bool = True
    noise_reduction_strength: float = 0.5
    normalize: bool = True
    compression: bool = True
    de_ess: bool = True
    eq_voice: bool = True


class MusicConfig(BaseModel):
    """Background music configuration."""

    enabled: bool = False
    genre: str = "ambient"
    volume_db: float = -20
    auto_duck: bool = True
    fade_in: float = 2.0
    fade_out: float = 3.0


class AIConfig(BaseModel):
    """AI configuration."""

    provider: str = "anthropic"
    model: str = "claude-sonnet-4-20250514"
    transcription_model: str = "base"
    title_count: int = 5
    tone: str = "professional"
    include_hashtags: bool = True
    include_chapters: bool = True


class ThumbnailConfig(BaseModel):
    """Thumbnail generation configuration."""

    width: int = 1280
    height: int = 720
    text_overlay: bool = True
    face_detection: bool = True
    style: str = "bold"


class YouTubeConfig(BaseModel):
    """YouTube upload configuration."""

    privacy: str = "private"
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
    threads: int = 0


class OutputConfig(BaseModel):
    """Output configuration."""

    format: str = "mp4"
    video_codec: str = "libx264"
    audio_codec: str = "aac"
    quality_preset: str = "medium"


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
