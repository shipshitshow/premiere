"""Tests for configuration management."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from premiere.utils.config import (
    AIConfig,
    AudioConfig,
    Config,
    MusicConfig,
    OutputConfig,
    ProcessingConfig,
    SilenceConfig,
    ThumbnailConfig,
    VideoConfig,
    YouTubeConfig,
    _deep_merge,
    get_config,
    get_temp_dir,
    load_config,
    set_config,
)


class TestSilenceConfig:
    """Tests for SilenceConfig."""

    def test_default_values(self):
        """Test default silence config values."""
        config = SilenceConfig()
        assert config.threshold_db == -40
        assert config.min_duration == 0.5
        assert config.padding == 0.1

    def test_custom_values(self):
        """Test custom silence config values."""
        config = SilenceConfig(threshold_db=-50, min_duration=1.0, padding=0.2)
        assert config.threshold_db == -50
        assert config.min_duration == 1.0
        assert config.padding == 0.2


class TestVideoConfig:
    """Tests for VideoConfig."""

    def test_default_values(self):
        """Test default video config values."""
        config = VideoConfig()
        assert config.target_resolution == "1080p"
        assert config.target_fps == 30
        assert config.stabilization is True
        assert config.color_correction is True

    def test_custom_values(self):
        """Test custom video config values."""
        config = VideoConfig(
            target_resolution="4k",
            target_fps=60,
            stabilization=False,
            stabilization_strength=0.8,
        )
        assert config.target_resolution == "4k"
        assert config.target_fps == 60
        assert config.stabilization is False
        assert config.stabilization_strength == 0.8


class TestAudioConfig:
    """Tests for AudioConfig."""

    def test_default_values(self):
        """Test default audio config values."""
        config = AudioConfig()
        assert config.target_lufs == -14
        assert config.noise_reduction is True
        assert config.normalize is True
        assert config.compression is True

    def test_custom_values(self):
        """Test custom audio config values."""
        config = AudioConfig(
            target_lufs=-16,
            noise_reduction=False,
            noise_reduction_strength=0.8,
        )
        assert config.target_lufs == -16
        assert config.noise_reduction is False
        assert config.noise_reduction_strength == 0.8


class TestMusicConfig:
    """Tests for MusicConfig."""

    def test_default_values(self):
        """Test default music config values."""
        config = MusicConfig()
        assert config.enabled is False
        assert config.genre == "ambient"
        assert config.volume_db == -20
        assert config.auto_duck is True


class TestAIConfig:
    """Tests for AIConfig."""

    def test_default_values(self):
        """Test default AI config values."""
        config = AIConfig()
        assert config.provider == "anthropic"
        assert "claude" in config.model.lower()
        assert config.title_count == 5
        assert config.tone == "professional"


class TestThumbnailConfig:
    """Tests for ThumbnailConfig."""

    def test_default_values(self):
        """Test default thumbnail config values."""
        config = ThumbnailConfig()
        assert config.width == 1280
        assert config.height == 720
        assert config.text_overlay is True
        assert config.style == "bold"


class TestYouTubeConfig:
    """Tests for YouTubeConfig."""

    def test_default_values(self):
        """Test default YouTube config values."""
        config = YouTubeConfig()
        assert config.privacy == "private"
        assert config.category == "22"
        assert config.notify_subscribers is False
        assert config.made_for_kids is False


class TestProcessingConfig:
    """Tests for ProcessingConfig."""

    def test_default_values(self):
        """Test default processing config values."""
        config = ProcessingConfig()
        assert config.temp_dir is None
        assert config.keep_temp is False
        assert config.gpu_acceleration is True
        assert config.threads == 0


class TestOutputConfig:
    """Tests for OutputConfig."""

    def test_default_values(self):
        """Test default output config values."""
        config = OutputConfig()
        assert config.format == "mp4"
        assert config.video_codec == "libx264"
        assert config.audio_codec == "aac"
        assert config.quality_preset == "medium"


class TestConfig:
    """Tests for main Config class."""

    def test_default_config(self):
        """Test creating config with defaults."""
        config = Config()
        assert isinstance(config.silence, SilenceConfig)
        assert isinstance(config.video, VideoConfig)
        assert isinstance(config.audio, AudioConfig)
        assert isinstance(config.music, MusicConfig)
        assert isinstance(config.ai, AIConfig)
        assert isinstance(config.thumbnail, ThumbnailConfig)
        assert isinstance(config.youtube, YouTubeConfig)
        assert isinstance(config.processing, ProcessingConfig)
        assert isinstance(config.output, OutputConfig)

    def test_config_with_nested_values(self):
        """Test creating config with nested values."""
        config = Config(
            silence=SilenceConfig(threshold_db=-50),
            video=VideoConfig(target_fps=60),
        )
        assert config.silence.threshold_db == -50
        assert config.video.target_fps == 60


class TestDeepMerge:
    """Tests for _deep_merge function."""

    def test_simple_merge(self):
        """Test merging simple dicts."""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        _deep_merge(base, override)
        assert base == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        """Test merging nested dicts."""
        base = {"a": {"x": 1, "y": 2}, "b": 3}
        override = {"a": {"y": 5, "z": 6}}
        _deep_merge(base, override)
        assert base == {"a": {"x": 1, "y": 5, "z": 6}, "b": 3}

    def test_deep_nested_merge(self):
        """Test deeply nested merging."""
        base = {"a": {"b": {"c": 1}}}
        override = {"a": {"b": {"d": 2}}}
        _deep_merge(base, override)
        assert base == {"a": {"b": {"c": 1, "d": 2}}}


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_config_default(self):
        """Test loading config without custom file."""
        with patch("premiere.utils.config.Path") as mock_path:
            mock_path.return_value.parent.parent.parent.parent.__truediv__.return_value.exists.return_value = False
            config = load_config()
        assert isinstance(config, Config)

    def test_load_config_from_file(self, temp_dir):
        """Test loading config from YAML file."""
        config_file = temp_dir / "config.yaml"
        config_data = {
            "silence": {"threshold_db": -50},
            "video": {"target_fps": 60},
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        with patch("premiere.utils.config.Path") as mock_path:
            # Make default config not exist
            mock_path.return_value.parent.parent.parent.parent.__truediv__.return_value.exists.return_value = False
            config = load_config(config_file)

        assert config.silence.threshold_db == -50
        assert config.video.target_fps == 60


class TestGetSetConfig:
    """Tests for get_config and set_config functions."""

    def test_get_config_creates_default(self):
        """Test that get_config creates default config."""
        config = get_config()
        assert isinstance(config, Config)

    def test_set_config_persists(self):
        """Test that set_config persists the config."""
        custom_config = Config(silence=SilenceConfig(threshold_db=-60))
        set_config(custom_config)

        retrieved = get_config()
        assert retrieved.silence.threshold_db == -60

    def test_get_config_returns_same_instance(self):
        """Test that get_config returns cached instance."""
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2


class TestGetTempDir:
    """Tests for get_temp_dir function."""

    def test_get_temp_dir_with_output_dir(self, temp_dir):
        """Test getting temp dir with output directory specified."""
        result = get_temp_dir(temp_dir)
        assert result == temp_dir / "temp"
        assert result.exists()

    def test_get_temp_dir_creates_directory(self, temp_dir):
        """Test that temp directory is created."""
        output_dir = temp_dir / "output"
        output_dir.mkdir()
        result = get_temp_dir(output_dir)
        assert result.exists()
        assert result.parent == output_dir

    def test_get_temp_dir_fallback_to_system(self, temp_dir):
        """Test fallback to system temp when not in project."""
        import os
        import tempfile as tf

        # Change to a temporary directory that doesn't have pyproject.toml
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_dir)
            # No pyproject.toml or src/premiere in temp_dir
            result = get_temp_dir()
            # Should use system temp
            assert str(tf.gettempdir()) in str(result) or "temp" in str(result).lower()
        finally:
            os.chdir(original_cwd)
