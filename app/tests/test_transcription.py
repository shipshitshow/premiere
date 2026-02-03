"""Tests for video transcription module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from premiere.generators.transcription import (
    Transcript,
    TranscriptSegment,
    _format_timestamp_simple,
    generate_chapters,
    generate_srt,
    save_transcript,
    transcribe_video,
)


class TestTranscriptSegment:
    """Tests for TranscriptSegment dataclass."""

    def test_create_segment(self):
        """Test creating a transcript segment."""
        segment = TranscriptSegment(start=0.0, end=5.0, text="Hello world")
        assert segment.start == 0.0
        assert segment.end == 5.0
        assert segment.text == "Hello world"


class TestTranscript:
    """Tests for Transcript dataclass."""

    def test_create_transcript(self):
        """Test creating a transcript."""
        segments = [
            TranscriptSegment(start=0.0, end=5.0, text="Hello"),
            TranscriptSegment(start=5.0, end=10.0, text="World"),
        ]
        transcript = Transcript(
            segments=segments, full_text="Hello World", language="en"
        )
        assert len(transcript.segments) == 2
        assert transcript.full_text == "Hello World"
        assert transcript.language == "en"


class TestTranscribeVideo:
    """Tests for transcribe_video function."""

    def test_transcribe_video_returns_transcript(self, mock_video_path, temp_dir):
        """Test that video transcription returns valid transcript."""
        mock_segments = [
            MagicMock(start=0.0, end=5.0, text="Hello and welcome"),
            MagicMock(start=5.0, end=10.0, text="to this video"),
        ]
        mock_info = MagicMock(language="en")

        with patch("premiere.generators.transcription.extract_audio") as mock_extract, patch(
            "premiere.generators.transcription.get_temp_dir", return_value=temp_dir
        ):
            mock_extract.return_value = temp_dir / "audio.wav"
            (temp_dir / "audio.wav").touch()

            with patch("faster_whisper.WhisperModel") as mock_model:
                mock_instance = MagicMock()
                mock_instance.transcribe.return_value = (mock_segments, mock_info)
                mock_model.return_value = mock_instance

                result = transcribe_video(mock_video_path, model_size="tiny")

        assert isinstance(result, Transcript)
        assert len(result.segments) == 2
        assert result.language == "en"

    def test_transcribe_video_uses_config_model(self, mock_video_path, temp_dir, test_config):
        """Test that default model comes from config."""
        mock_segments = []
        mock_info = MagicMock(language="en")

        with patch("premiere.generators.transcription.extract_audio") as mock_extract, patch(
            "premiere.generators.transcription.get_temp_dir", return_value=temp_dir
        ):
            mock_extract.return_value = temp_dir / "audio.wav"
            (temp_dir / "audio.wav").touch()

            with patch("faster_whisper.WhisperModel") as mock_model:
                mock_instance = MagicMock()
                mock_instance.transcribe.return_value = (mock_segments, mock_info)
                mock_model.return_value = mock_instance

                transcribe_video(mock_video_path)

                # Should use config default model
                mock_model.assert_called_once()


class TestGenerateSrt:
    """Tests for generate_srt function."""

    def test_generate_srt_creates_file(self, temp_dir, mock_transcript):
        """Test that SRT file is created with correct format."""
        output_path = temp_dir / "subtitle.srt"

        generate_srt(mock_transcript, output_path)

        assert output_path.exists()
        content = output_path.read_text()

        # Check SRT format
        assert "1\n" in content
        assert "-->" in content
        assert "Hello and welcome" in content

    def test_generate_srt_timestamp_format(self, temp_dir):
        """Test that timestamps are formatted correctly for SRT."""
        transcript = Transcript(
            segments=[
                TranscriptSegment(start=3661.5, end=3665.75, text="Test"),
            ],
            full_text="Test",
            language="en",
        )
        output_path = temp_dir / "subtitle.srt"

        generate_srt(transcript, output_path)

        content = output_path.read_text()
        # 3661.5 seconds = 1:01:01,500
        assert "01:01:01,500" in content


class TestGenerateChapters:
    """Tests for generate_chapters function."""

    def test_generate_chapters_with_gaps(self, mock_transcript):
        """Test chapter generation with significant gaps."""
        chapters = generate_chapters(mock_transcript, min_gap=30.0)

        # Should have chapters at significant gaps
        assert len(chapters) >= 1
        assert "time" in chapters[0]
        assert "title" in chapters[0]

    def test_generate_chapters_empty_transcript(self):
        """Test chapter generation with empty transcript."""
        transcript = Transcript(segments=[], full_text="", language="en")
        chapters = generate_chapters(transcript)
        assert chapters == []

    def test_generate_chapters_title_truncation(self):
        """Test that long titles are truncated."""
        transcript = Transcript(
            segments=[
                TranscriptSegment(
                    start=0.0,
                    end=5.0,
                    text="This is a very long segment text that should be truncated in the chapter title",
                ),
            ],
            full_text="This is a very long segment text",
            language="en",
        )
        chapters = generate_chapters(transcript, min_gap=0)

        assert len(chapters) == 1
        assert len(chapters[0]["title"]) <= 30


class TestSaveTranscript:
    """Tests for save_transcript function."""

    def test_save_transcript_json(self, temp_dir, mock_transcript):
        """Test saving transcript as JSON."""
        output_path = temp_dir / "transcript.json"

        save_transcript(mock_transcript, output_path, format="json")

        assert output_path.exists()
        import json

        data = json.loads(output_path.read_text())
        assert "language" in data
        assert "full_text" in data
        assert "segments" in data
        assert len(data["segments"]) == len(mock_transcript.segments)

    def test_save_transcript_markdown(self, temp_dir, mock_transcript):
        """Test saving transcript as Markdown."""
        output_path = temp_dir / "transcript.md"

        save_transcript(mock_transcript, output_path, format="md")

        assert output_path.exists()
        content = output_path.read_text()
        assert "# Transcript" in content
        assert "**Language:**" in content
        assert mock_transcript.full_text in content

    def test_save_transcript_text(self, temp_dir, mock_transcript):
        """Test saving transcript as plain text."""
        output_path = temp_dir / "transcript.txt"

        save_transcript(mock_transcript, output_path, format="txt")

        assert output_path.exists()
        content = output_path.read_text()
        assert content == mock_transcript.full_text


class TestFormatTimestampSimple:
    """Tests for _format_timestamp_simple function."""

    def test_format_seconds_only(self):
        """Test formatting times under a minute."""
        assert _format_timestamp_simple(45.0) == "0:45"

    def test_format_minutes_and_seconds(self):
        """Test formatting times with minutes."""
        assert _format_timestamp_simple(125.0) == "2:05"

    def test_format_hours(self):
        """Test formatting times with hours."""
        assert _format_timestamp_simple(3665.0) == "1:01:05"

    def test_format_zero(self):
        """Test formatting zero seconds."""
        assert _format_timestamp_simple(0.0) == "0:00"
