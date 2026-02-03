"""Integration tests for the video processing pipeline."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from premiere.pipeline import Pipeline, PipelineResult, PipelineStep, quick_process


class TestPipelineStep:
    """Tests for PipelineStep enum."""

    def test_all_steps_defined(self):
        """Test that all expected steps are defined."""
        expected_steps = [
            "CUT_SILENCE",
            "ENHANCE_VIDEO",
            "ENHANCE_AUDIO",
            "ADD_MUSIC",
            "TRANSCRIBE",
            "GENERATE_CLIPS",
            "GENERATE_METADATA",
            "GENERATE_THUMBNAIL",
            "UPLOAD",
        ]
        for step_name in expected_steps:
            assert hasattr(PipelineStep, step_name)


class TestPipelineResult:
    """Tests for PipelineResult dataclass."""

    def test_default_values(self):
        """Test default PipelineResult values."""
        result = PipelineResult()
        assert result.output_path is None
        assert result.transcript is None
        assert result.transcript_path is None
        assert result.metadata is None
        assert result.thumbnail_path is None
        assert result.clips == []
        assert result.clips_dir is None
        assert result.upload_result is None
        assert result.errors == []
        assert result.steps_completed == []

    def test_with_values(self, temp_dir, mock_transcript):
        """Test PipelineResult with values."""
        result = PipelineResult(
            output_path=temp_dir / "output.mp4",
            transcript=mock_transcript,
            errors=["Warning 1"],
            steps_completed=[PipelineStep.CUT_SILENCE],
        )
        assert result.output_path == temp_dir / "output.mp4"
        assert result.transcript is not None
        assert len(result.errors) == 1
        assert len(result.steps_completed) == 1


class TestPipeline:
    """Tests for Pipeline class."""

    def test_pipeline_init_default_steps(self, test_config):
        """Test pipeline initialization with default steps."""
        pipeline = Pipeline()
        # Default should include all steps except GENERATE_CLIPS
        assert PipelineStep.CUT_SILENCE in pipeline.steps
        assert PipelineStep.ENHANCE_VIDEO in pipeline.steps
        assert PipelineStep.ENHANCE_AUDIO in pipeline.steps
        assert PipelineStep.TRANSCRIBE in pipeline.steps
        assert PipelineStep.GENERATE_CLIPS not in pipeline.steps

    def test_pipeline_init_custom_steps(self, test_config):
        """Test pipeline initialization with custom steps."""
        custom_steps = [PipelineStep.CUT_SILENCE, PipelineStep.ENHANCE_AUDIO]
        pipeline = Pipeline(steps=custom_steps)
        assert pipeline.steps == custom_steps

    def test_pipeline_run_nonexistent_video(self, temp_dir, test_config):
        """Test pipeline run with non-existent video."""
        pipeline = Pipeline()
        result = pipeline.run(temp_dir / "nonexistent.mp4")
        assert "not found" in result.errors[0].lower()

    def test_pipeline_run_silence_step(self, mock_video_path, temp_dir, test_config):
        """Test pipeline runs silence removal step."""
        pipeline = Pipeline(steps=[PipelineStep.CUT_SILENCE])

        with patch("premiere.pipeline.cut_silence") as mock_cut, patch(
            "premiere.pipeline.get_temp_dir", return_value=temp_dir
        ):
            mock_output = temp_dir / "silence_removed.mp4"
            mock_output.touch()
            mock_cut.return_value = mock_output

            result = pipeline.run(mock_video_path, output_dir=temp_dir)

        assert mock_cut.called
        assert PipelineStep.CUT_SILENCE in result.steps_completed

    def test_pipeline_run_video_step(
        self, mock_video_path, temp_dir, test_config, mock_video_info
    ):
        """Test pipeline runs video enhancement step."""
        pipeline = Pipeline(steps=[PipelineStep.ENHANCE_VIDEO])

        with patch("premiere.pipeline.enhance_video") as mock_enhance, patch(
            "premiere.pipeline.get_temp_dir", return_value=temp_dir
        ):
            mock_output = temp_dir / "video_enhanced.mp4"
            mock_output.touch()
            mock_enhance.return_value = mock_output

            result = pipeline.run(mock_video_path, output_dir=temp_dir)

        assert mock_enhance.called
        assert PipelineStep.ENHANCE_VIDEO in result.steps_completed

    def test_pipeline_run_audio_step(self, mock_video_path, temp_dir, test_config):
        """Test pipeline runs audio enhancement step."""
        pipeline = Pipeline(steps=[PipelineStep.ENHANCE_AUDIO])

        with patch("premiere.pipeline.enhance_audio") as mock_enhance, patch(
            "premiere.pipeline.get_temp_dir", return_value=temp_dir
        ):
            mock_output = temp_dir / "audio_enhanced.mp4"
            mock_output.touch()
            mock_enhance.return_value = mock_output

            result = pipeline.run(mock_video_path, output_dir=temp_dir)

        assert mock_enhance.called
        assert PipelineStep.ENHANCE_AUDIO in result.steps_completed

    def test_pipeline_run_transcribe_step(
        self, mock_video_path, temp_dir, test_config, mock_transcript
    ):
        """Test pipeline runs transcription step."""
        pipeline = Pipeline(steps=[PipelineStep.TRANSCRIBE])

        with patch("premiere.pipeline.transcribe_video") as mock_transcribe, patch(
            "premiere.pipeline.save_transcript"
        ) as mock_save, patch(
            "premiere.pipeline.get_temp_dir", return_value=temp_dir
        ):
            mock_transcribe.return_value = mock_transcript
            mock_save.return_value = temp_dir / "transcript.md"

            result = pipeline.run(mock_video_path, output_dir=temp_dir)

        assert mock_transcribe.called
        assert result.transcript is not None
        assert PipelineStep.TRANSCRIBE in result.steps_completed

    def test_pipeline_run_metadata_step(
        self, mock_video_path, temp_dir, test_config, mock_transcript
    ):
        """Test pipeline runs metadata generation step."""
        pipeline = Pipeline(steps=[PipelineStep.TRANSCRIBE, PipelineStep.GENERATE_METADATA])

        mock_metadata = MagicMock(
            titles=["Test Title"],
            description="Test description",
            tags=["test"],
            chapters=[],
        )

        with patch("premiere.pipeline.transcribe_video") as mock_transcribe, patch(
            "premiere.pipeline.save_transcript"
        ), patch("premiere.pipeline.generate_metadata") as mock_gen_meta, patch(
            "premiere.pipeline.get_temp_dir", return_value=temp_dir
        ):
            mock_transcribe.return_value = mock_transcript
            mock_gen_meta.return_value = mock_metadata

            result = pipeline.run(mock_video_path, output_dir=temp_dir)

        assert mock_gen_meta.called
        assert result.metadata is not None
        assert PipelineStep.GENERATE_METADATA in result.steps_completed

    def test_pipeline_run_thumbnail_step(self, mock_video_path, temp_dir, test_config):
        """Test pipeline runs thumbnail generation step."""
        pipeline = Pipeline(steps=[PipelineStep.GENERATE_THUMBNAIL])

        with patch("premiere.pipeline.generate_thumbnail") as mock_thumb, patch(
            "premiere.pipeline.get_temp_dir", return_value=temp_dir
        ):
            thumb_path = temp_dir / "thumbnail.jpg"
            thumb_path.touch()
            mock_thumb.return_value = thumb_path

            result = pipeline.run(mock_video_path, output_dir=temp_dir)

        assert mock_thumb.called
        assert PipelineStep.GENERATE_THUMBNAIL in result.steps_completed

    def test_pipeline_handles_step_error(self, mock_video_path, temp_dir, test_config):
        """Test pipeline handles step errors gracefully."""
        pipeline = Pipeline(steps=[PipelineStep.CUT_SILENCE, PipelineStep.ENHANCE_AUDIO])

        with patch("premiere.pipeline.cut_silence") as mock_cut, patch(
            "premiere.pipeline.enhance_audio"
        ) as mock_enhance, patch(
            "premiere.pipeline.get_temp_dir", return_value=temp_dir
        ):
            mock_cut.side_effect = Exception("Cut failed")
            mock_output = temp_dir / "audio_enhanced.mp4"
            mock_output.touch()
            mock_enhance.return_value = mock_output

            result = pipeline.run(mock_video_path, output_dir=temp_dir)

        # Should have error for cut_silence but still complete enhance_audio
        assert any("CUT_SILENCE" in err for err in result.errors)
        assert PipelineStep.ENHANCE_AUDIO in result.steps_completed

    def test_pipeline_clips_added_when_requested(
        self, mock_video_path, temp_dir, test_config, mock_transcript, mock_video_info
    ):
        """Test that clips step is added when generate_clips=True."""
        pipeline = Pipeline(steps=[PipelineStep.TRANSCRIBE])

        with patch("premiere.pipeline.transcribe_video") as mock_transcribe, patch(
            "premiere.pipeline.save_transcript"
        ), patch("premiere.pipeline.probe") as mock_probe, patch(
            "premiere.pipeline.detect_viral_moments"
        ) as mock_detect, patch(
            "premiere.pipeline.extract_clips"
        ) as mock_extract, patch(
            "premiere.pipeline.save_clips_manifest"
        ), patch(
            "premiere.pipeline.get_temp_dir", return_value=temp_dir
        ):
            mock_transcribe.return_value = mock_transcript
            mock_probe.return_value = mock_video_info
            mock_detect.return_value = [
                MagicMock(start=10.0, end=30.0, score=8, hook="Great moment")
            ]
            mock_extract.return_value = [MagicMock(path=temp_dir / "clip1.mp4")]

            result = pipeline.run(
                mock_video_path, output_dir=temp_dir, generate_clips=True
            )

        assert PipelineStep.GENERATE_CLIPS in result.steps_completed
        assert len(result.clips) > 0

    def test_pipeline_upload_skipped_when_not_requested(
        self, mock_video_path, temp_dir, test_config
    ):
        """Test that upload step is skipped when upload=False."""
        pipeline = Pipeline(steps=[PipelineStep.UPLOAD])

        with patch("premiere.pipeline.get_temp_dir", return_value=temp_dir):
            result = pipeline.run(mock_video_path, output_dir=temp_dir, upload=False)

        assert PipelineStep.UPLOAD not in result.steps_completed

    def test_pipeline_cleanup_temp_files(self, mock_video_path, temp_dir, test_config):
        """Test that pipeline cleans up temp files."""
        pipeline = Pipeline(steps=[])

        with patch("premiere.pipeline.get_temp_dir", return_value=temp_dir), patch(
            "shutil.rmtree"
        ) as mock_rmtree:
            pipeline.run(mock_video_path, output_dir=temp_dir)

        # rmtree should be called for cleanup
        assert mock_rmtree.called


class TestQuickProcess:
    """Tests for quick_process function."""

    def test_quick_process_creates_pipeline(self, mock_video_path, temp_dir, test_config):
        """Test that quick_process creates and runs a pipeline."""
        with patch.object(Pipeline, "run") as mock_run:
            mock_run.return_value = PipelineResult()
            quick_process(mock_video_path)

        assert mock_run.called

    def test_quick_process_passes_options(self, mock_video_path, temp_dir, test_config):
        """Test that quick_process passes options to pipeline."""
        with patch.object(Pipeline, "run") as mock_run:
            mock_run.return_value = PipelineResult()
            quick_process(
                mock_video_path,
                output_path=temp_dir / "output.mp4",
                upload=True,
                generate_clips=True,
            )

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs.get("upload") is True
        assert call_kwargs.get("generate_clips") is True
