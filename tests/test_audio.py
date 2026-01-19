"""Tests for audio enhancement processor."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from premiere.processors.audio import enhance_audio, measure_loudness
from premiere.utils.config import AudioConfig


class TestEnhanceAudio:
    """Tests for enhance_audio function."""

    def test_enhance_audio_applies_filters(self, mock_video_path, temp_dir, test_config):
        """Test that audio enhancement applies configured filters."""
        output_path = temp_dir / "output.mp4"

        with patch("premiere.processors.audio.run_ffmpeg") as mock_run:
            enhance_audio(mock_video_path, output_path)

        assert mock_run.called
        call_args = mock_run.call_args[0][0]
        # Check that audio filter flag is present
        assert "-af" in call_args

    def test_enhance_audio_no_filters_copies_file(self, mock_video_path, temp_dir):
        """Test that when no filters enabled, file is copied."""
        output_path = temp_dir / "output.mp4"
        config = AudioConfig(
            noise_reduction=False,
            de_ess=False,
            eq_voice=False,
            compression=False,
            normalize=False,
        )

        with patch("premiere.processors.audio.run_ffmpeg") as mock_run, patch(
            "premiere.processors.audio.get_config"
        ) as mock_get_config:
            mock_get_config.return_value = MagicMock(audio=config)
            enhance_audio(mock_video_path, output_path)

        assert mock_run.called
        call_args = mock_run.call_args[0][0]
        # Should use copy codec when no filters
        assert "-c" in call_args
        assert "copy" in call_args

    def test_enhance_audio_noise_reduction_filter(self, mock_video_path, temp_dir):
        """Test that noise reduction filter is applied correctly."""
        output_path = temp_dir / "output.mp4"
        config = AudioConfig(
            noise_reduction=True,
            noise_reduction_strength=0.5,
            de_ess=False,
            eq_voice=False,
            compression=False,
            normalize=False,
        )

        with patch("premiere.processors.audio.run_ffmpeg") as mock_run, patch(
            "premiere.processors.audio.get_config"
        ) as mock_get_config:
            mock_get_config.return_value = MagicMock(audio=config)
            enhance_audio(mock_video_path, output_path)

        call_args = mock_run.call_args[0][0]
        af_index = call_args.index("-af")
        filter_chain = call_args[af_index + 1]
        assert "afftdn" in filter_chain

    def test_enhance_audio_de_esser_filter(self, mock_video_path, temp_dir):
        """Test that de-esser filter is applied when enabled."""
        output_path = temp_dir / "output.mp4"
        config = AudioConfig(
            noise_reduction=False,
            de_ess=True,
            eq_voice=False,
            compression=False,
            normalize=False,
        )

        with patch("premiere.processors.audio.run_ffmpeg") as mock_run, patch(
            "premiere.processors.audio.get_config"
        ) as mock_get_config:
            mock_get_config.return_value = MagicMock(audio=config)
            enhance_audio(mock_video_path, output_path)

        call_args = mock_run.call_args[0][0]
        af_index = call_args.index("-af")
        filter_chain = call_args[af_index + 1]
        assert "deesser" in filter_chain

    def test_enhance_audio_eq_voice_filter(self, mock_video_path, temp_dir):
        """Test that voice EQ filters are applied when enabled."""
        output_path = temp_dir / "output.mp4"
        config = AudioConfig(
            noise_reduction=False,
            de_ess=False,
            eq_voice=True,
            compression=False,
            normalize=False,
        )

        with patch("premiere.processors.audio.run_ffmpeg") as mock_run, patch(
            "premiere.processors.audio.get_config"
        ) as mock_get_config:
            mock_get_config.return_value = MagicMock(audio=config)
            enhance_audio(mock_video_path, output_path)

        call_args = mock_run.call_args[0][0]
        af_index = call_args.index("-af")
        filter_chain = call_args[af_index + 1]
        assert "equalizer" in filter_chain

    def test_enhance_audio_compression_filter(self, mock_video_path, temp_dir):
        """Test that compression filter is applied when enabled."""
        output_path = temp_dir / "output.mp4"
        config = AudioConfig(
            noise_reduction=False,
            de_ess=False,
            eq_voice=False,
            compression=True,
            normalize=False,
        )

        with patch("premiere.processors.audio.run_ffmpeg") as mock_run, patch(
            "premiere.processors.audio.get_config"
        ) as mock_get_config:
            mock_get_config.return_value = MagicMock(audio=config)
            enhance_audio(mock_video_path, output_path)

        call_args = mock_run.call_args[0][0]
        af_index = call_args.index("-af")
        filter_chain = call_args[af_index + 1]
        assert "acompressor" in filter_chain

    def test_enhance_audio_loudnorm_filter(self, mock_video_path, temp_dir):
        """Test that loudness normalization filter is applied when enabled."""
        output_path = temp_dir / "output.mp4"
        config = AudioConfig(
            noise_reduction=False,
            de_ess=False,
            eq_voice=False,
            compression=False,
            normalize=True,
            target_lufs=-14,
        )

        with patch("premiere.processors.audio.run_ffmpeg") as mock_run, patch(
            "premiere.processors.audio.get_config"
        ) as mock_get_config:
            mock_get_config.return_value = MagicMock(audio=config)
            enhance_audio(mock_video_path, output_path)

        call_args = mock_run.call_args[0][0]
        af_index = call_args.index("-af")
        filter_chain = call_args[af_index + 1]
        assert "loudnorm" in filter_chain
        assert "I=-14" in filter_chain

    def test_enhance_audio_custom_config(self, mock_video_path, temp_dir):
        """Test that custom config is used when provided."""
        output_path = temp_dir / "output.mp4"
        custom_config = AudioConfig(
            noise_reduction=True,
            de_ess=False,
            eq_voice=False,
            compression=False,
            normalize=True,
            target_lufs=-16,
        )

        with patch("premiere.processors.audio.run_ffmpeg") as mock_run:
            enhance_audio(mock_video_path, output_path, config=custom_config)

        call_args = mock_run.call_args[0][0]
        af_index = call_args.index("-af")
        filter_chain = call_args[af_index + 1]
        assert "I=-16" in filter_chain


class TestMeasureLoudness:
    """Tests for measure_loudness function."""

    def test_measure_loudness_parses_output(self, mock_video_path):
        """Test that loudness measurement parses FFmpeg output."""
        mock_stderr = """
{
    "input_i": "-18.5",
    "input_tp": "-3.2",
    "input_lra": "8.1",
    "input_thresh": "-28.5"
}
"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr=mock_stderr)
            result = measure_loudness(mock_video_path)

        assert result["input_i"] == -18.5
        assert result["input_tp"] == -3.2
        assert result["input_lra"] == 8.1
        assert result["input_thresh"] == -28.5

    def test_measure_loudness_handles_missing_values(self, mock_video_path):
        """Test that missing values are handled gracefully."""
        mock_stderr = "No loudness data"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr=mock_stderr)
            result = measure_loudness(mock_video_path)

        assert result["input_i"] is None
        assert result["input_tp"] is None
