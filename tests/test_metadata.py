"""Tests for metadata generation."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from premiere.generators.metadata import (
    VideoMetadata,
    _parse_metadata_response,
    format_description_with_chapters,
    generate_metadata,
)
from premiere.generators.transcription import Transcript, TranscriptSegment


class TestVideoMetadata:
    """Tests for VideoMetadata dataclass."""

    def test_create_metadata(self):
        """Test creating video metadata."""
        metadata = VideoMetadata(
            titles=["Title 1", "Title 2"],
            description="Test description",
            tags=["tag1", "tag2"],
            chapters=[{"time": 0, "title": "Intro"}],
            hashtags=["#test"],
        )
        assert len(metadata.titles) == 2
        assert metadata.description == "Test description"
        assert len(metadata.tags) == 2
        assert len(metadata.chapters) == 1
        assert metadata.hashtags == ["#test"]

    def test_create_metadata_without_hashtags(self):
        """Test creating metadata without hashtags."""
        metadata = VideoMetadata(
            titles=["Title"],
            description="Description",
            tags=["tag"],
            chapters=[],
        )
        assert metadata.hashtags is None


class TestParseMetadataResponse:
    """Tests for _parse_metadata_response function."""

    def test_parse_complete_response(self, mock_transcript):
        """Test parsing a complete AI response."""
        response = """
TITLES:
1. Amazing Video Title One
2. Incredible Content Title Two
3. Best Video Title Three

DESCRIPTION:
This is a great video about testing.
It covers many important topics.
Watch till the end!

TAGS:
testing, video, content, youtube, tutorial

HASHTAGS:
#testing #youtube #video
"""
        config = MagicMock(include_chapters=False)
        result = _parse_metadata_response(response, mock_transcript, config)

        assert len(result.titles) == 3
        assert result.titles[0] == "Amazing Video Title One"
        assert "great video" in result.description
        assert "testing" in result.tags
        assert "#testing" in result.hashtags

    def test_parse_response_without_hashtags(self, mock_transcript):
        """Test parsing response without hashtags section."""
        response = """
TITLES:
1. Test Title

DESCRIPTION:
Test description.

TAGS:
tag1, tag2
"""
        config = MagicMock(include_chapters=False)
        result = _parse_metadata_response(response, mock_transcript, config)

        assert len(result.titles) == 1
        assert result.description == "Test description."
        assert len(result.tags) == 2
        assert result.hashtags == []

    def test_parse_response_with_chapters(self, mock_transcript):
        """Test parsing response with chapter generation."""
        response = """
TITLES:
1. Test Title

DESCRIPTION:
Test description.

TAGS:
tag1
"""
        config = MagicMock(include_chapters=True)
        result = _parse_metadata_response(response, mock_transcript, config)

        # Should have generated chapters from transcript
        assert isinstance(result.chapters, list)

    def test_parse_response_handles_malformed_titles(self, mock_transcript):
        """Test parsing handles malformed title formats."""
        response = """
TITLES:
1) Title One
2. Title Two
3 - Title Three
- Title Four

DESCRIPTION:
Description

TAGS:
tag
"""
        config = MagicMock(include_chapters=False)
        result = _parse_metadata_response(response, mock_transcript, config)

        # Should extract titles despite varying formats
        assert len(result.titles) >= 2


class TestGenerateMetadata:
    """Tests for generate_metadata function."""

    def test_generate_metadata_with_claude_cli(self, mock_transcript, mock_video_path, temp_dir):
        """Test metadata generation using Claude CLI."""
        mock_response = """
TITLES:
1. Test Generated Title

DESCRIPTION:
Generated description.

TAGS:
test, generated
"""
        with patch(
            "premiere.generators.metadata._generate_with_claude_cli"
        ) as mock_generate:
            mock_generate.return_value = VideoMetadata(
                titles=["Test Generated Title"],
                description="Generated description.",
                tags=["test", "generated"],
                chapters=[],
            )
            result = generate_metadata(
                mock_transcript, mock_video_path, use_claude_cli=True
            )

        assert isinstance(result, VideoMetadata)
        assert len(result.titles) >= 1

    def test_generate_metadata_with_anthropic_api(
        self, mock_transcript, mock_video_path, temp_dir
    ):
        """Test metadata generation using Anthropic API."""
        with patch("premiere.generators.metadata.get_config") as mock_config, patch(
            "anthropic.Anthropic"
        ) as mock_client:
            mock_config.return_value = MagicMock(
                ai=MagicMock(
                    provider="anthropic",
                    model="claude-3-sonnet",
                    title_count=3,
                    tone="professional",
                    include_hashtags=True,
                    include_chapters=False,
                ),
                anthropic_api_key="test-key",
            )
            mock_client.return_value.messages.create.return_value = MagicMock(
                content=[
                    MagicMock(
                        text="""
TITLES:
1. API Generated Title

DESCRIPTION:
API generated description.

TAGS:
api, test
"""
                    )
                ]
            )
            result = generate_metadata(
                mock_transcript, mock_video_path, use_claude_cli=False
            )

        assert isinstance(result, VideoMetadata)

    def test_generate_metadata_unknown_provider_raises(self, mock_transcript):
        """Test that unknown provider raises error."""
        with patch("premiere.generators.metadata.get_config") as mock_config:
            mock_config.return_value = MagicMock(
                ai=MagicMock(provider="unknown"),
            )
            with pytest.raises(ValueError, match="Unknown AI provider"):
                generate_metadata(mock_transcript, use_claude_cli=False)


class TestFormatDescriptionWithChapters:
    """Tests for format_description_with_chapters function."""

    def test_format_with_chapters(self):
        """Test adding chapters to description."""
        description = "This is the video description."
        chapters = [
            {"time": 0, "title": "Introduction"},
            {"time": 60, "title": "Main Content"},
            {"time": 180, "title": "Conclusion"},
        ]

        result = format_description_with_chapters(description, chapters)

        assert "This is the video description." in result
        assert "Chapters:" in result
        assert "0:00 - Introduction" in result
        assert "1:00 - Main Content" in result
        assert "3:00 - Conclusion" in result

    def test_format_without_chapters(self):
        """Test that empty chapters returns original description."""
        description = "Original description."
        result = format_description_with_chapters(description, [])
        assert result == description

    def test_format_chapter_time_formatting(self):
        """Test chapter time formatting."""
        chapters = [
            {"time": 0, "title": "Start"},
            {"time": 65, "title": "One Minute"},
            {"time": 3665, "title": "One Hour"},
        ]

        result = format_description_with_chapters("Desc", chapters)

        assert "0:00" in result
        assert "1:05" in result
        assert "61:05" in result  # Hours shown as minutes
