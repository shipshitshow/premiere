"""Tests for video enhancement processor."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from premiere.processors.video import enhance_video, extract_keyframes
from premiere.utils.config import VideoConfig


class TestEnhanceVideo:
    """Tests for enhance_video function."""

    def test_enhance_video_applies_filters(
        self, mock_video_path, temp_dir, test_config, mock_video_info
    ):
        """Test that video enhancement applies configured filters."""
        output_path = temp_dir / "output.mp4"

        with patch("premiere.processors.video.run_ffmpeg") as mock_run, patch(
            "premiere.processors.video.probe", return_value=mock_video_info
        ), patch("premiere.processors.video.check_vidstab_support", return_value=False):
            enhance_video(mock_video_path, output_path)

        assert mock_run.called

    def test_enhance_video_no_filters_copies_file(
        self, mock_video_path, temp_dir, mock_video_info
    ):
        """Test that when no filters needed, file is copied."""
        output_path = temp_dir / "output.mp4"
        # Match source video dimensions so no scaling needed
        mock_video_info.width = 1920
        mock_video_info.height = 1080
        mock_video_info.fps = 30.0

        config = VideoConfig(
            target_resolution="1080p",
            target_fps=30,
            stabilization=False,
            color_correction=False,
        )

        with patch("premiere.processors.video.run_ffmpeg") as mock_run, patch(
            "premiere.processors.video.probe", return_value=mock_video_info
        ), patch("premiere.processors.video.get_config") as mock_get_config:
            mock_get_config.return_value = MagicMock(
                video=config, output=MagicMock(quality_preset="medium")
            )
            enhance_video(mock_video_path, output_path, config=config)

        call_args = mock_run.call_args[0][0]
        assert "-c" in call_args
        assert "copy" in call_args

    def test_enhance_video_scaling_filter(self, mock_video_path, temp_dir, mock_video_info):
        """Test that scaling filter is applied when resolution differs."""
        output_path = temp_dir / "output.mp4"
        # Set source to different resolution
        mock_video_info.width = 3840
        mock_video_info.height = 2160

        config = VideoConfig(
            target_resolution="1080p",
            target_fps=30,
            stabilization=False,
            color_correction=False,
        )

        with patch("premiere.processors.video.run_ffmpeg") as mock_run, patch(
            "premiere.processors.video.probe", return_value=mock_video_info
        ), patch("premiere.processors.video.get_config") as mock_get_config:
            mock_get_config.return_value = MagicMock(
                video=config, output=MagicMock(quality_preset="medium")
            )
            enhance_video(mock_video_path, output_path, config=config)

        call_args = mock_run.call_args[0][0]
        vf_index = call_args.index("-vf")
        filter_chain = call_args[vf_index + 1]
        assert "scale=" in filter_chain
        assert "1920" in filter_chain
        assert "1080" in filter_chain

    def test_enhance_video_fps_conversion(self, mock_video_path, temp_dir, mock_video_info):
        """Test that FPS conversion filter is applied when needed."""
        output_path = temp_dir / "output.mp4"
        mock_video_info.fps = 60.0  # Source is 60fps

        config = VideoConfig(
            target_resolution="1080p",
            target_fps=30,  # Target is 30fps
            stabilization=False,
            color_correction=False,
        )

        with patch("premiere.processors.video.run_ffmpeg") as mock_run, patch(
            "premiere.processors.video.probe", return_value=mock_video_info
        ), patch("premiere.processors.video.get_config") as mock_get_config:
            mock_get_config.return_value = MagicMock(
                video=config, output=MagicMock(quality_preset="medium")
            )
            enhance_video(mock_video_path, output_path, config=config)

        call_args = mock_run.call_args[0][0]
        vf_index = call_args.index("-vf")
        filter_chain = call_args[vf_index + 1]
        assert "fps=30" in filter_chain

    def test_enhance_video_color_correction(self, mock_video_path, temp_dir, mock_video_info):
        """Test that color correction filters are applied when enabled."""
        output_path = temp_dir / "output.mp4"

        config = VideoConfig(
            target_resolution="1080p",
            target_fps=30,
            stabilization=False,
            color_correction=True,
        )

        with patch("premiere.processors.video.run_ffmpeg") as mock_run, patch(
            "premiere.processors.video.probe", return_value=mock_video_info
        ), patch("premiere.processors.video.get_config") as mock_get_config:
            mock_get_config.return_value = MagicMock(
                video=config, output=MagicMock(quality_preset="medium")
            )
            enhance_video(mock_video_path, output_path, config=config)

        call_args = mock_run.call_args[0][0]
        vf_index = call_args.index("-vf")
        filter_chain = call_args[vf_index + 1]
        assert "colorlevels" in filter_chain or "eq=" in filter_chain

    def test_enhance_video_stabilization_with_vidstab(
        self, mock_video_path, temp_dir, mock_video_info
    ):
        """Test that stabilization uses two-pass process when vidstab is available."""
        output_path = temp_dir / "output.mp4"

        config = VideoConfig(
            target_resolution="1080p",
            target_fps=30,
            stabilization=True,
            stabilization_strength=0.5,
            color_correction=False,
        )

        with patch("premiere.processors.video.run_ffmpeg") as mock_run, patch(
            "premiere.processors.video.probe", return_value=mock_video_info
        ), patch("premiere.processors.video.check_vidstab_support", return_value=True), patch(
            "premiere.processors.video.get_config"
        ) as mock_get_config, patch(
            "premiere.processors.video.get_temp_dir", return_value=temp_dir
        ):
            mock_get_config.return_value = MagicMock(
                video=config, output=MagicMock(quality_preset="medium")
            )
            enhance_video(mock_video_path, output_path, config=config)

        # Should have two FFmpeg calls (analysis + transform)
        assert mock_run.call_count >= 2

    def test_enhance_video_stabilization_skipped_without_vidstab(
        self, mock_video_path, temp_dir, mock_video_info
    ):
        """Test that stabilization is skipped when vidstab not available."""
        output_path = temp_dir / "output.mp4"

        config = VideoConfig(
            target_resolution="1080p",
            target_fps=30,
            stabilization=True,
            color_correction=False,
        )

        with patch("premiere.processors.video.run_ffmpeg") as mock_run, patch(
            "premiere.processors.video.probe", return_value=mock_video_info
        ), patch("premiere.processors.video.check_vidstab_support", return_value=False), patch(
            "premiere.processors.video.get_config"
        ) as mock_get_config:
            mock_get_config.return_value = MagicMock(
                video=config, output=MagicMock(quality_preset="medium")
            )
            enhance_video(mock_video_path, output_path, config=config)

        # Should only have one FFmpeg call (no stabilization)
        assert mock_run.call_count == 1


class TestExtractKeyframes:
    """Tests for extract_keyframes function."""

    def test_extract_keyframes_creates_frames(
        self, mock_video_path, temp_dir, mock_video_info
    ):
        """Test that keyframes are extracted correctly."""
        output_dir = temp_dir / "frames"

        with patch("premiere.processors.video.run_ffmpeg") as mock_run, patch(
            "premiere.processors.video.probe", return_value=mock_video_info
        ):
            # Simulate created files
            def create_frame(*args, **kwargs):
                output_dir.mkdir(parents=True, exist_ok=True)
                # Extract frame number from args
                for i, arg in enumerate(args[0]):
                    if str(output_dir) in arg:
                        Path(arg).touch()
                return MagicMock(returncode=0)

            mock_run.side_effect = create_frame
            frames = extract_keyframes(mock_video_path, output_dir, count=5)

        assert mock_run.call_count == 5  # One call per frame
        assert len(frames) == 5

    def test_extract_keyframes_calculates_intervals(
        self, mock_video_path, temp_dir, mock_video_info
    ):
        """Test that frame extraction uses correct time intervals."""
        output_dir = temp_dir / "frames"
        mock_video_info.duration = 100.0  # 100 second video

        timestamps = []

        def capture_timestamp(*args, **kwargs):
            cmd = args[0]
            for i, arg in enumerate(cmd):
                if arg == "-ss":
                    timestamps.append(float(cmd[i + 1]))
            output_dir.mkdir(parents=True, exist_ok=True)
            return MagicMock(returncode=0)

        with patch("premiere.processors.video.run_ffmpeg", side_effect=capture_timestamp), patch(
            "premiere.processors.video.probe", return_value=mock_video_info
        ):
            extract_keyframes(mock_video_path, output_dir, count=4)

        # With 100s duration and 4 frames, interval should be 20s
        # Frames at: 20, 40, 60, 80
        assert len(timestamps) == 4
        assert abs(timestamps[0] - 20.0) < 0.1
        assert abs(timestamps[1] - 40.0) < 0.1
        assert abs(timestamps[2] - 60.0) < 0.1
        assert abs(timestamps[3] - 80.0) < 0.1

    def test_extract_keyframes_creates_output_dir(
        self, mock_video_path, temp_dir, mock_video_info
    ):
        """Test that output directory is created if it doesn't exist."""
        output_dir = temp_dir / "nested" / "frames"
        assert not output_dir.exists()

        with patch("premiere.processors.video.run_ffmpeg") as mock_run, patch(
            "premiere.processors.video.probe", return_value=mock_video_info
        ):
            mock_run.return_value = MagicMock(returncode=0)
            extract_keyframes(mock_video_path, output_dir, count=1)

        assert output_dir.exists()
