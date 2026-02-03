"""Tests for silence detection and removal processor."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from premiere.processors.silence import (
    AudioSegment,
    SilenceSegment,
    cut_silence,
    detect_silence,
    get_audio_segments,
)
from premiere.utils.ffmpeg import FFmpegError


class TestSilenceSegment:
    """Tests for SilenceSegment dataclass."""

    def test_create_segment(self):
        """Test creating a silence segment."""
        segment = SilenceSegment(start=5.0, end=10.0, duration=5.0)
        assert segment.start == 5.0
        assert segment.end == 10.0
        assert segment.duration == 5.0


class TestAudioSegment:
    """Tests for AudioSegment dataclass."""

    def test_create_segment(self):
        """Test creating an audio segment."""
        segment = AudioSegment(start=0.0, end=5.0)
        assert segment.start == 0.0
        assert segment.end == 5.0


class TestDetectSilence:
    """Tests for detect_silence function."""

    def test_detect_silence_parses_ffmpeg_output(self, mock_video_path, test_config):
        """Test that silence detection parses FFmpeg output correctly."""
        mock_stderr = """
[silencedetect @ 0x1234] silence_start: 5.0
[silencedetect @ 0x1234] silence_end: 8.0 | silence_duration: 3.0
[silencedetect @ 0x1234] silence_start: 20.0
[silencedetect @ 0x1234] silence_end: 25.5 | silence_duration: 5.5
"""
        with patch("subprocess.run") as mock_run, patch(
            "premiere.processors.silence.check_ffmpeg", return_value=True
        ):
            mock_run.return_value = MagicMock(returncode=0, stderr=mock_stderr)
            segments = detect_silence(mock_video_path)

        assert len(segments) == 2
        assert segments[0].start == 5.0
        assert segments[0].end == 8.0
        assert segments[0].duration == 3.0
        assert segments[1].start == 20.0
        assert segments[1].end == 25.5
        assert segments[1].duration == 5.5

    def test_detect_silence_no_silence(self, mock_video_path, test_config):
        """Test when no silence is detected."""
        with patch("subprocess.run") as mock_run, patch(
            "premiere.processors.silence.check_ffmpeg", return_value=True
        ):
            mock_run.return_value = MagicMock(returncode=0, stderr="No silence detected")
            segments = detect_silence(mock_video_path)

        assert len(segments) == 0

    def test_detect_silence_uses_custom_threshold(self, mock_video_path, test_config):
        """Test that custom threshold is used."""
        with patch("subprocess.run") as mock_run, patch(
            "premiere.processors.silence.check_ffmpeg", return_value=True
        ):
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            detect_silence(mock_video_path, threshold_db=-50, min_duration=1.0)

        call_args = mock_run.call_args[0][0]
        assert "noise=-50dB:d=1.0" in " ".join(call_args)


class TestGetAudioSegments:
    """Tests for get_audio_segments function."""

    def test_no_silence_returns_full_video(self, test_config):
        """Test that no silence returns single segment of full video."""
        segments = get_audio_segments([], video_duration=100.0)
        assert len(segments) == 1
        assert segments[0].start == 0.0
        assert segments[0].end == 100.0

    def test_single_silence_creates_two_segments(self, test_config):
        """Test that single silence creates two audio segments."""
        silence = [SilenceSegment(start=40.0, end=50.0, duration=10.0)]
        segments = get_audio_segments(silence, video_duration=100.0, padding=0.0)

        assert len(segments) == 2
        assert segments[0].start == 0.0
        assert segments[0].end == 40.0
        assert segments[1].start == 50.0
        assert segments[1].end == 100.0

    def test_multiple_silences(self, test_config):
        """Test handling multiple silence segments."""
        silences = [
            SilenceSegment(start=10.0, end=15.0, duration=5.0),
            SilenceSegment(start=30.0, end=40.0, duration=10.0),
            SilenceSegment(start=70.0, end=80.0, duration=10.0),
        ]
        segments = get_audio_segments(silences, video_duration=100.0, padding=0.0)

        assert len(segments) == 4
        assert segments[0].end == 10.0
        assert segments[1].start == 15.0
        assert segments[1].end == 30.0
        assert segments[2].start == 40.0
        assert segments[2].end == 70.0
        assert segments[3].start == 80.0
        assert segments[3].end == 100.0

    def test_padding_applied(self, test_config):
        """Test that padding is applied to segments."""
        silence = [SilenceSegment(start=40.0, end=50.0, duration=10.0)]
        segments = get_audio_segments(silence, video_duration=100.0, padding=0.5)

        assert len(segments) == 2
        assert segments[0].end == 40.5  # start + padding
        assert segments[1].start == 49.5  # end - padding


class TestCutSilence:
    """Tests for cut_silence function."""

    def test_cut_silence_no_silence_copies_file(self, mock_video_path, temp_dir, test_config):
        """Test that when no silence detected, file is copied."""
        output_path = temp_dir / "output.mp4"

        with patch(
            "premiere.processors.silence.detect_silence", return_value=[]
        ), patch("premiere.processors.silence.run_ffmpeg") as mock_run:
            cut_silence(mock_video_path, output_path)

        # Should call ffmpeg with copy codec
        assert mock_run.called
        call_args = mock_run.call_args[0][0]
        assert "-c" in call_args
        assert "copy" in call_args

    def test_cut_silence_with_silence_segments(
        self, mock_video_path, temp_dir, test_config, mock_video_info
    ):
        """Test cutting silence with detected segments."""
        output_path = temp_dir / "output.mp4"
        silence = [SilenceSegment(start=40.0, end=50.0, duration=10.0)]

        with patch(
            "premiere.processors.silence.detect_silence", return_value=silence
        ), patch("premiere.utils.ffmpeg.probe", return_value=mock_video_info), patch(
            "premiere.processors.silence.run_ffmpeg"
        ) as mock_run, patch(
            "premiere.processors.silence.get_temp_dir", return_value=temp_dir
        ):
            cut_silence(mock_video_path, output_path)

        # Should have multiple FFmpeg calls (segment extraction + concat)
        assert mock_run.call_count >= 2

    def test_cut_silence_raises_error_on_empty_result(
        self, mock_video_path, temp_dir, test_config, mock_video_info
    ):
        """Test that error is raised when no segments remain."""
        output_path = temp_dir / "output.mp4"

        # Silence that spans entire video
        mock_video_info.duration = 10.0
        silence = [SilenceSegment(start=0.0, end=10.0, duration=10.0)]

        with patch(
            "premiere.processors.silence.detect_silence", return_value=silence
        ), patch("premiere.utils.ffmpeg.probe", return_value=mock_video_info), patch(
            "premiere.processors.silence.get_audio_segments", return_value=[]
        ):
            with pytest.raises(FFmpegError, match="No audio segments"):
                cut_silence(mock_video_path, output_path)
