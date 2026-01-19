"""Pytest configuration and shared fixtures."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from premiere.utils.config import (
    AudioConfig,
    Config,
    SilenceConfig,
    ThumbnailConfig,
    VideoConfig,
    set_config,
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_video_path(temp_dir):
    """Create a mock video file path."""
    video_path = temp_dir / "test_video.mp4"
    video_path.touch()
    return video_path


@pytest.fixture
def mock_audio_path(temp_dir):
    """Create a mock audio file path."""
    audio_path = temp_dir / "test_audio.wav"
    audio_path.touch()
    return audio_path


@pytest.fixture
def mock_image_path(temp_dir):
    """Create a mock image file for thumbnail tests."""
    from PIL import Image

    img_path = temp_dir / "test_frame.jpg"
    # Create a simple test image (100x100 RGB)
    img = Image.new("RGB", (100, 100), color=(128, 128, 128))
    img.save(img_path, "JPEG")
    return img_path


@pytest.fixture
def mock_video_info():
    """Create mock video info data."""
    from premiere.utils.ffmpeg import VideoInfo

    return VideoInfo(
        path=Path("/tmp/test.mp4"),
        duration=120.0,
        width=1920,
        height=1080,
        fps=30.0,
        video_codec="h264",
        audio_codec="aac",
        audio_sample_rate=48000,
        audio_channels=2,
        file_size=10000000,
        bitrate=1000000,
    )


@pytest.fixture
def mock_transcript():
    """Create mock transcript data."""
    from premiere.generators.transcription import Transcript, TranscriptSegment

    return Transcript(
        segments=[
            TranscriptSegment(start=0.0, end=5.0, text="Hello and welcome to the video."),
            TranscriptSegment(start=5.0, end=10.0, text="Today we'll discuss testing."),
            TranscriptSegment(start=10.0, end=15.0, text="Testing is very important."),
            TranscriptSegment(start=15.0, end=20.0, text="Let's dive into the details."),
            TranscriptSegment(start=50.0, end=55.0, text="Now for the exciting part."),
            TranscriptSegment(start=55.0, end=60.0, text="This is absolutely amazing content."),
        ],
        full_text="Hello and welcome to the video. Today we'll discuss testing. Testing is very important. Let's dive into the details. Now for the exciting part. This is absolutely amazing content.",
        language="en",
    )


@pytest.fixture
def test_config():
    """Create a test configuration."""
    config = Config(
        silence=SilenceConfig(threshold_db=-40, min_duration=0.5, padding=0.1),
        video=VideoConfig(
            target_resolution="1080p",
            target_fps=30,
            stabilization=False,
            color_correction=True,
        ),
        audio=AudioConfig(
            target_lufs=-14,
            noise_reduction=True,
            normalize=True,
            compression=True,
        ),
        thumbnail=ThumbnailConfig(
            width=1280,
            height=720,
            text_overlay=True,
            face_detection=False,
            style="bold",
        ),
    )
    set_config(config)
    return config


@pytest.fixture
def mock_ffmpeg():
    """Mock FFmpeg-related functions."""
    with patch("premiere.utils.ffmpeg.check_ffmpeg", return_value=True), patch(
        "premiere.utils.ffmpeg.run_ffmpeg"
    ) as mock_run, patch("premiere.utils.ffmpeg.probe") as mock_probe:
        # Configure mock probe to return realistic data
        mock_probe.return_value = MagicMock(
            duration=120.0,
            width=1920,
            height=1080,
            fps=30.0,
            video_codec="h264",
            audio_codec="aac",
        )
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        yield {"run": mock_run, "probe": mock_probe}


@pytest.fixture
def mock_subprocess():
    """Mock subprocess.run for FFmpeg commands."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="",
            stderr="[silencedetect @ 0x1234] silence_start: 5.0\n"
            "[silencedetect @ 0x1234] silence_end: 8.0 | silence_duration: 3.0\n",
        )
        yield mock_run


@pytest.fixture(autouse=True)
def reset_config():
    """Reset global config before each test."""
    from premiere.utils import config as config_module

    config_module._config = None
    yield
    config_module._config = None


@pytest.fixture(autouse=True)
def reset_logger():
    """Reset global logger before each test."""
    from premiere.utils import logger as logger_module

    logger_module._logger = None
    yield
    logger_module._logger = None
