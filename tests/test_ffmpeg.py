"""Tests for FFmpeg utilities."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from premiere.utils.ffmpeg import (
    FFmpegError,
    VideoInfo,
    check_ffmpeg,
    check_vidstab_support,
    extract_audio,
    get_resolution_dimensions,
    probe,
    run_ffmpeg,
)


class TestVideoInfo:
    """Tests for VideoInfo dataclass."""

    def test_create_video_info(self):
        """Test creating VideoInfo."""
        info = VideoInfo(
            path=Path("/test/video.mp4"),
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
        assert info.duration == 120.0
        assert info.width == 1920
        assert info.height == 1080
        assert info.fps == 30.0


class TestFFmpegError:
    """Tests for FFmpegError exception."""

    def test_error_message(self):
        """Test error message."""
        error = FFmpegError("Test error message")
        assert str(error) == "Test error message"


class TestCheckFfmpeg:
    """Tests for check_ffmpeg function."""

    def test_ffmpeg_available(self):
        """Test when FFmpeg is available."""
        with patch("shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/ffmpeg"
            result = check_ffmpeg()
        assert result is True

    def test_ffmpeg_not_found(self):
        """Test when FFmpeg is not installed."""
        with patch("shutil.which") as mock_which:
            mock_which.side_effect = [None, "/usr/bin/ffprobe"]
            with pytest.raises(FFmpegError, match="FFmpeg not found"):
                check_ffmpeg()

    def test_ffprobe_not_found(self):
        """Test when ffprobe is not installed."""
        with patch("shutil.which") as mock_which:
            mock_which.side_effect = ["/usr/bin/ffmpeg", None]
            with pytest.raises(FFmpegError, match="ffprobe not found"):
                check_ffmpeg()


class TestCheckVidstabSupport:
    """Tests for check_vidstab_support function."""

    def test_vidstab_available(self):
        """Test when vidstab filters are available."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="vidstabdetect\nvidstabtransform\n"
            )
            result = check_vidstab_support()
        assert result is True

    def test_vidstab_not_available(self):
        """Test when vidstab filters are not available."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="scale\ncrop\n")
            result = check_vidstab_support()
        assert result is False

    def test_vidstab_check_error(self):
        """Test when FFmpeg command fails."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            result = check_vidstab_support()
        assert result is False


class TestProbe:
    """Tests for probe function."""

    def test_probe_returns_video_info(self, mock_video_path):
        """Test that probe returns VideoInfo."""
        mock_output = {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "r_frame_rate": "30/1",
                },
                {
                    "codec_type": "audio",
                    "codec_name": "aac",
                    "sample_rate": "48000",
                    "channels": 2,
                },
            ],
            "format": {
                "duration": "120.5",
                "size": "10000000",
                "bit_rate": "1000000",
            },
        }

        with patch("subprocess.run") as mock_run, patch(
            "premiere.utils.ffmpeg.check_ffmpeg", return_value=True
        ):
            mock_run.return_value = MagicMock(
                returncode=0, stdout=json.dumps(mock_output)
            )
            result = probe(mock_video_path)

        assert isinstance(result, VideoInfo)
        assert result.duration == 120.5
        assert result.width == 1920
        assert result.height == 1080
        assert result.fps == 30.0
        assert result.video_codec == "h264"
        assert result.audio_codec == "aac"

    def test_probe_file_not_found(self, temp_dir):
        """Test probe with non-existent file."""
        with patch("premiere.utils.ffmpeg.check_ffmpeg", return_value=True):
            with pytest.raises(FFmpegError, match="not found"):
                probe(temp_dir / "nonexistent.mp4")

    def test_probe_no_video_stream(self, mock_video_path):
        """Test probe when no video stream found."""
        mock_output = {
            "streams": [{"codec_type": "audio"}],
            "format": {},
        }

        with patch("subprocess.run") as mock_run, patch(
            "premiere.utils.ffmpeg.check_ffmpeg", return_value=True
        ):
            mock_run.return_value = MagicMock(
                returncode=0, stdout=json.dumps(mock_output)
            )
            with pytest.raises(FFmpegError, match="No video stream"):
                probe(mock_video_path)

    def test_probe_fractional_fps(self, mock_video_path):
        """Test probe with fractional frame rate."""
        mock_output = {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "r_frame_rate": "30000/1001",  # 29.97 fps
                }
            ],
            "format": {"duration": "60", "size": "1000", "bit_rate": "1000"},
        }

        with patch("subprocess.run") as mock_run, patch(
            "premiere.utils.ffmpeg.check_ffmpeg", return_value=True
        ):
            mock_run.return_value = MagicMock(
                returncode=0, stdout=json.dumps(mock_output)
            )
            result = probe(mock_video_path)

        assert abs(result.fps - 29.97) < 0.01


class TestRunFfmpeg:
    """Tests for run_ffmpeg function."""

    def test_run_ffmpeg_success(self):
        """Test successful FFmpeg execution."""
        with patch("subprocess.run") as mock_run, patch(
            "premiere.utils.ffmpeg.check_ffmpeg", return_value=True
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = run_ffmpeg(["-i", "input.mp4", "output.mp4"])

        assert mock_run.called
        # Check that standard flags are added
        call_args = mock_run.call_args[0][0]
        assert "-y" in call_args
        assert "-hide_banner" in call_args

    def test_run_ffmpeg_failure(self):
        """Test FFmpeg execution failure."""
        import subprocess

        with patch("subprocess.run") as mock_run, patch(
            "premiere.utils.ffmpeg.check_ffmpeg", return_value=True
        ):
            mock_run.side_effect = subprocess.CalledProcessError(
                1, "ffmpeg", stderr="Error: Invalid input"
            )
            with pytest.raises(FFmpegError, match="Invalid input"):
                run_ffmpeg(["-i", "input.mp4", "output.mp4"])

    def test_run_ffmpeg_filters_warnings(self):
        """Test that non-critical warnings are filtered."""
        with patch("subprocess.run") as mock_run, patch(
            "premiere.utils.ffmpeg.check_ffmpeg", return_value=True
        ):
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="",
                stderr="Your platform doesn't support hardware accelerated AV1 decoding",
            )
            # Should not raise despite stderr output
            result = run_ffmpeg(["-i", "input.mp4", "output.mp4"])
            assert result is not None


class TestExtractAudio:
    """Tests for extract_audio function."""

    def test_extract_audio_calls_ffmpeg(self, mock_video_path, temp_dir):
        """Test that audio extraction calls FFmpeg correctly."""
        output_path = temp_dir / "audio.wav"

        with patch("premiere.utils.ffmpeg.run_ffmpeg") as mock_run:
            extract_audio(mock_video_path, output_path)

        assert mock_run.called
        call_args = mock_run.call_args[0][0]
        assert "-vn" in call_args  # No video
        assert "-acodec" in call_args or "-c:a" in " ".join(call_args)


class TestGetResolutionDimensions:
    """Tests for get_resolution_dimensions function."""

    def test_720p(self):
        """Test 720p resolution."""
        width, height = get_resolution_dimensions("720p")
        assert width == 1280
        assert height == 720

    def test_1080p(self):
        """Test 1080p resolution."""
        width, height = get_resolution_dimensions("1080p")
        assert width == 1920
        assert height == 1080

    def test_1440p(self):
        """Test 1440p resolution."""
        width, height = get_resolution_dimensions("1440p")
        assert width == 2560
        assert height == 1440

    def test_4k(self):
        """Test 4K resolution."""
        width, height = get_resolution_dimensions("4k")
        assert width == 3840
        assert height == 2160

    def test_2160p(self):
        """Test 2160p (4K alternative)."""
        width, height = get_resolution_dimensions("2160p")
        assert width == 3840
        assert height == 2160

    def test_unknown_defaults_to_1080p(self):
        """Test unknown resolution defaults to 1080p."""
        width, height = get_resolution_dimensions("unknown")
        assert width == 1920
        assert height == 1080

    def test_case_insensitive(self):
        """Test resolution strings are case insensitive."""
        width, height = get_resolution_dimensions("4K")
        assert width == 3840
        assert height == 2160
