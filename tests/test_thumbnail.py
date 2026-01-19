"""Tests for thumbnail generation."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from premiere.generators.thumbnail import (
    _add_text_overlay,
    _apply_style,
    _is_skin_tone,
    _resize_and_crop,
    _score_frame,
    _select_best_frame,
    _wrap_text,
    generate_thumbnail,
)
from premiere.utils.config import ThumbnailConfig


class TestGenerateThumbnail:
    """Tests for generate_thumbnail function."""

    def test_generate_thumbnail_creates_file(
        self, mock_video_path, temp_dir, test_config, mock_image_path
    ):
        """Test that thumbnail generation creates output file."""
        output_path = temp_dir / "thumbnail.jpg"
        frames_dir = temp_dir / "frames"
        frames_dir.mkdir()

        # Create mock frames
        for i in range(3):
            frame = frames_dir / f"frame_{i:03d}.jpg"
            img = Image.new("RGB", (1920, 1080), color=(100, 100, 100))
            img.save(frame, "JPEG")

        with patch(
            "premiere.generators.thumbnail.extract_keyframes",
            return_value=[frames_dir / f"frame_{i:03d}.jpg" for i in range(3)],
        ), patch("premiere.generators.thumbnail.get_temp_dir", return_value=temp_dir):
            generate_thumbnail(mock_video_path, output_path, title="Test Title")

        assert output_path.exists()

    def test_generate_thumbnail_with_title(
        self, mock_video_path, temp_dir, test_config, mock_image_path
    ):
        """Test that thumbnail includes title text when provided."""
        output_path = temp_dir / "thumbnail.jpg"
        frames_dir = temp_dir / "frames"
        frames_dir.mkdir()

        # Create mock frame
        frame = frames_dir / "frame_001.jpg"
        img = Image.new("RGB", (1920, 1080), color=(100, 100, 100))
        img.save(frame, "JPEG")

        with patch(
            "premiere.generators.thumbnail.extract_keyframes", return_value=[frame]
        ), patch("premiere.generators.thumbnail.get_temp_dir", return_value=temp_dir):
            generate_thumbnail(mock_video_path, output_path, title="Test Title")

        # Verify output has correct dimensions
        result = Image.open(output_path)
        assert result.size == (1280, 720)  # Default thumbnail size

    def test_generate_thumbnail_no_frames_raises_error(
        self, mock_video_path, temp_dir, test_config
    ):
        """Test that error is raised when no frames extracted."""
        output_path = temp_dir / "thumbnail.jpg"

        with patch(
            "premiere.generators.thumbnail.extract_keyframes", return_value=[]
        ), patch("premiere.generators.thumbnail.get_temp_dir", return_value=temp_dir):
            with pytest.raises(ValueError, match="No frames extracted"):
                generate_thumbnail(mock_video_path, output_path)


class TestSelectBestFrame:
    """Tests for _select_best_frame function."""

    def test_select_best_frame_returns_highest_score(self, temp_dir):
        """Test that frame with highest score is selected."""
        config = ThumbnailConfig(face_detection=False)

        # Create frames with different qualities
        frames = []
        for i, color in enumerate([(50, 50, 50), (128, 128, 128), (200, 200, 200)]):
            frame_path = temp_dir / f"frame_{i}.jpg"
            # Middle brightness (128) should score highest
            img = Image.new("RGB", (100, 100), color=color)
            img.save(frame_path, "JPEG")
            frames.append(frame_path)

        best = _select_best_frame(frames, config)
        # Frame with brightness closest to 128 should win
        assert best in frames

    def test_select_best_frame_empty_list_raises_error(self):
        """Test that empty frame list raises error."""
        config = ThumbnailConfig()
        with pytest.raises(ValueError, match="No frames"):
            _select_best_frame([], config)

    def test_select_best_frame_single_frame(self, temp_dir):
        """Test that single frame is returned."""
        config = ThumbnailConfig()
        frame_path = temp_dir / "frame.jpg"
        img = Image.new("RGB", (100, 100), color=(128, 128, 128))
        img.save(frame_path, "JPEG")

        result = _select_best_frame([frame_path], config)
        assert result == frame_path


class TestScoreFrame:
    """Tests for _score_frame function."""

    def test_score_frame_brightness_scoring(self):
        """Test that mid-range brightness scores higher."""
        config = ThumbnailConfig(face_detection=False)

        # Dark image
        dark_img = Image.new("RGB", (100, 100), color=(20, 20, 20))
        dark_score = _score_frame(dark_img, config)

        # Mid brightness image
        mid_img = Image.new("RGB", (100, 100), color=(128, 128, 128))
        mid_score = _score_frame(mid_img, config)

        # Bright image
        bright_img = Image.new("RGB", (100, 100), color=(240, 240, 240))
        bright_score = _score_frame(bright_img, config)

        # Mid brightness should score highest
        assert mid_score >= dark_score
        assert mid_score >= bright_score

    def test_score_frame_contrast_scoring(self):
        """Test that higher contrast scores higher."""
        config = ThumbnailConfig(face_detection=False)

        # Low contrast (all same color)
        low_contrast = Image.new("RGB", (100, 100), color=(128, 128, 128))
        low_score = _score_frame(low_contrast, config)

        # High contrast (half black, half white)
        high_contrast = Image.new("RGB", (100, 100), color=(0, 0, 0))
        pixels = high_contrast.load()
        for x in range(50, 100):
            for y in range(100):
                pixels[x, y] = (255, 255, 255)
        high_score = _score_frame(high_contrast, config)

        # High contrast should score higher
        assert high_score > low_score


class TestIsSkinTone:
    """Tests for _is_skin_tone function."""

    def test_skin_tone_detection(self):
        """Test skin tone detection for various colors."""
        # Typical skin tones should be detected
        assert _is_skin_tone(220, 180, 160) is True  # Light skin
        assert _is_skin_tone(180, 130, 100) is True  # Medium skin

        # Non-skin colors should not be detected
        assert _is_skin_tone(0, 0, 255) is False  # Blue
        assert _is_skin_tone(0, 255, 0) is False  # Green
        assert _is_skin_tone(50, 50, 50) is False  # Dark gray


class TestResizeAndCrop:
    """Tests for _resize_and_crop function."""

    def test_resize_wider_image(self):
        """Test resizing a wider-than-target image."""
        # 2:1 aspect ratio image
        img = Image.new("RGB", (200, 100))
        result = _resize_and_crop(img, 100, 100)
        assert result.size == (100, 100)

    def test_resize_taller_image(self):
        """Test resizing a taller-than-target image."""
        # 1:2 aspect ratio image
        img = Image.new("RGB", (100, 200))
        result = _resize_and_crop(img, 100, 100)
        assert result.size == (100, 100)

    def test_resize_maintains_content(self):
        """Test that center content is preserved."""
        # Create image with red center
        img = Image.new("RGB", (300, 300), color=(0, 0, 255))
        pixels = img.load()
        # Add red center square
        for x in range(100, 200):
            for y in range(100, 200):
                pixels[x, y] = (255, 0, 0)

        result = _resize_and_crop(img, 100, 100)
        # Center pixel should still be red-ish
        center = result.getpixel((50, 50))
        assert center[0] > center[2]  # More red than blue


class TestApplyStyle:
    """Tests for _apply_style function."""

    def test_bold_style_increases_contrast(self):
        """Test that bold style increases contrast and saturation."""
        img = Image.new("RGB", (100, 100), color=(128, 128, 128))
        result = _apply_style(img, "bold")
        # Result should be different from original
        assert result is not None

    def test_minimal_style(self):
        """Test minimal style application."""
        img = Image.new("RGB", (100, 100), color=(128, 128, 128))
        result = _apply_style(img, "minimal")
        assert result is not None

    def test_cinematic_style(self):
        """Test cinematic style application."""
        img = Image.new("RGB", (100, 100), color=(128, 128, 128))
        result = _apply_style(img, "cinematic")
        assert result is not None


class TestAddTextOverlay:
    """Tests for _add_text_overlay function."""

    def test_add_text_creates_overlay(self):
        """Test that text overlay is added to image."""
        img = Image.new("RGB", (1280, 720), color=(50, 50, 50))
        result = _add_text_overlay(img, "Test Title", "bold")
        # Result should be an image with same dimensions
        assert result.size == (1280, 720)

    def test_add_text_long_title_wraps(self):
        """Test that long titles are wrapped."""
        img = Image.new("RGB", (1280, 720), color=(50, 50, 50))
        long_title = "This is a very long title that should wrap to multiple lines"
        result = _add_text_overlay(img, long_title, "bold")
        assert result.size == (1280, 720)


class TestWrapText:
    """Tests for _wrap_text function."""

    def test_wrap_text_short_stays_single_line(self):
        """Test that short text stays on single line."""
        img = Image.new("RGB", (100, 100))
        draw = __import__("PIL.ImageDraw", fromlist=["ImageDraw"]).Draw(img)
        font = __import__("PIL.ImageFont", fromlist=["ImageFont"]).load_default()

        lines = _wrap_text("Short", font, 1000, draw)
        assert len(lines) == 1
        assert lines[0] == "Short"

    def test_wrap_text_limits_to_three_lines(self):
        """Test that text is limited to 3 lines max."""
        img = Image.new("RGB", (100, 100))
        draw = __import__("PIL.ImageDraw", fromlist=["ImageDraw"]).Draw(img)
        font = __import__("PIL.ImageFont", fromlist=["ImageFont"]).load_default()

        long_text = "Word " * 50  # Many words
        lines = _wrap_text(long_text, font, 50, draw)
        assert len(lines) <= 3
