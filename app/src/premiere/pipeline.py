"""Video processing pipeline orchestrator."""

import shutil
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path

from rich.progress import Progress, SpinnerColumn, TextColumn

from premiere.generators.clips import GeneratedClip, detect_viral_moments, extract_clips, save_clips_manifest
from premiere.generators.metadata import VideoMetadata, generate_metadata
from premiere.generators.transcription import Transcript, save_transcript, transcribe_video
from premiere.processors.audio import enhance_audio
from premiere.processors.music import add_background_music
from premiere.processors.silence import cut_silence
from premiere.processors.video import enhance_video
from premiere.uploaders.youtube import upload_video
from premiere.utils.config import Config, get_config, get_temp_dir
from premiere.utils.ffmpeg import probe
from premiere.utils.logger import get_console, get_logger


class PipelineStep(Enum):
    """Pipeline processing steps."""

    CUT_SILENCE = auto()
    ENHANCE_VIDEO = auto()
    ENHANCE_AUDIO = auto()
    ADD_MUSIC = auto()
    TRANSCRIBE = auto()
    GENERATE_CLIPS = auto()
    GENERATE_METADATA = auto()
    UPLOAD = auto()


@dataclass
class PipelineResult:
    """Result of pipeline execution."""

    output_path: Path | None = None
    transcript: Transcript | None = None
    transcript_path: Path | None = None
    metadata: VideoMetadata | None = None
    clips: list[GeneratedClip] = field(default_factory=list)
    clips_dir: Path | None = None
    upload_result: dict | None = None
    errors: list[str] = field(default_factory=list)
    steps_completed: list[PipelineStep] = field(default_factory=list)


class Pipeline:
    """Video processing pipeline."""

    def __init__(
        self,
        config: Config | None = None,
        steps: list[PipelineStep] | None = None,
    ):
        """Initialize pipeline.

        Args:
            config: Configuration (default from global).
            steps: Steps to execute (default: all except clips).
        """
        self.config = config or get_config()
        # Default steps exclude clips (opt-in)
        if steps is None:
            self.steps = [s for s in PipelineStep if s != PipelineStep.GENERATE_CLIPS]
        else:
            self.steps = steps
        self.logger = get_logger()
        self.console = get_console()

    def run(
        self,
        video_path: Path,
        output_path: Path | None = None,
        output_dir: Path | None = None,
        upload: bool = False,
        generate_clips: bool = False,
        max_clips: int = 5,
    ) -> PipelineResult:
        """Run the video processing pipeline.

        Args:
            video_path: Input video file.
            output_path: Output video path (default: input_processed.mp4).
            output_dir: Directory for all outputs (default: video parent).
            upload: Whether to upload to YouTube.
            generate_clips: Generate viral short clips.
            max_clips: Maximum number of clips to generate.

        Returns:
            PipelineResult with outputs and status.
        """
        self.logger.info(f"Starting pipeline for {video_path.name}")

        if not video_path.exists():
            return PipelineResult(errors=[f"Video not found: {video_path}"])

        result = PipelineResult()

        # Set output directory
        if output_dir is None:
            output_dir = video_path.parent

        # Set default output path
        if output_path is None:
            output_path = output_dir / f"{video_path.stem}_processed.mp4"

        # Add clips step if requested
        steps = list(self.steps)
        if generate_clips and PipelineStep.GENERATE_CLIPS not in steps:
            # Insert after transcribe
            try:
                idx = steps.index(PipelineStep.TRANSCRIBE) + 1
            except ValueError:
                idx = 0
            steps.insert(idx, PipelineStep.GENERATE_CLIPS)

        # Create temp directory for intermediate files in output directory
        temp_base = get_temp_dir(output_dir)
        temp_path = temp_base / f"premiere_{int(time.time())}"
        temp_path.mkdir(parents=True, exist_ok=True)
        
        try:
            current_video = video_path

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console,
            ) as progress:
                # Process steps
                for step in steps:
                    if step == PipelineStep.UPLOAD and not upload:
                        continue

                    task_name = step.name.replace("_", " ").title()
                    task = progress.add_task(f"[cyan]{task_name}...", total=None)

                    try:
                        current_video, result = self._run_step(
                            step, current_video, temp_path, output_dir, result, max_clips
                        )
                        result.steps_completed.append(step)
                        progress.update(task, description=f"[green]{task_name} ✓")
                    except Exception as e:
                        self.logger.error(f"Step {step.name} failed: {e}")
                        result.errors.append(f"{step.name}: {e}")
                        progress.update(task, description=f"[red]{task_name} ✗")

            # Copy final output
            if current_video != video_path and current_video.exists():
                shutil.copy2(current_video, output_path)
                result.output_path = output_path
                self.logger.info(f"Output saved to {output_path}")
        finally:
            # Clean up temp directory if keep_temp is False
            if not self.config.processing.keep_temp and temp_path.exists():
                shutil.rmtree(temp_path, ignore_errors=True)

        return result

    def _run_step(
        self,
        step: PipelineStep,
        video_path: Path,
        temp_dir: Path,
        output_dir: Path,
        result: PipelineResult,
        max_clips: int = 5,
    ) -> tuple[Path, PipelineResult]:
        """Run a single pipeline step."""
        if step == PipelineStep.CUT_SILENCE:
            output = temp_dir / "silence_removed.mp4"
            cut_silence(video_path, output, **self._silence_kwargs())
            return output, result

        elif step == PipelineStep.ENHANCE_VIDEO:
            output = temp_dir / "video_enhanced.mp4"
            enhance_video(video_path, output, self.config.video)
            return output, result

        elif step == PipelineStep.ENHANCE_AUDIO:
            output = temp_dir / "audio_enhanced.mp4"
            enhance_audio(video_path, output, self.config.audio)
            return output, result

        elif step == PipelineStep.ADD_MUSIC:
            if not self.config.music.enabled:
                return video_path, result
            output = temp_dir / "music_added.mp4"
            add_background_music(video_path, output, config=self.config.music)
            return output, result

        elif step == PipelineStep.TRANSCRIBE:
            result.transcript = transcribe_video(
                video_path,
                self.config.ai.transcription_model,
            )
            # Save transcript to output directory
            transcript_path = output_dir / f"{video_path.stem}_transcript.md"
            save_transcript(result.transcript, transcript_path, format="md")
            result.transcript_path = transcript_path
            return video_path, result

        elif step == PipelineStep.GENERATE_CLIPS:
            if result.transcript is None:
                result.transcript = transcribe_video(video_path)

            # Get video duration
            info = probe(video_path)

            # Detect viral moments
            candidates = detect_viral_moments(
                result.transcript,
                info.duration,
                max_clips=max_clips,
            )

            if candidates:
                # Extract clips
                clips_dir = output_dir / f"{video_path.stem}_clips"
                result.clips = extract_clips(
                    video_path,
                    candidates,
                    clips_dir,
                    result.transcript,
                    vertical=True,
                )
                result.clips_dir = clips_dir

                # Save manifest
                save_clips_manifest(result.clips, clips_dir / "manifest.json")

            return video_path, result

        elif step == PipelineStep.GENERATE_METADATA:
            if result.transcript is None:
                result.transcript = transcribe_video(video_path)
            result.metadata = generate_metadata(result.transcript, video_path)
            return video_path, result

        elif step == PipelineStep.UPLOAD:
            if result.metadata is None:
                raise ValueError("Metadata required for upload")
            result.upload_result = upload_video(
                video_path,
                result.metadata,
                None,
                self.config.youtube,
            )
            return video_path, result

        return video_path, result

    def _silence_kwargs(self) -> dict:
        """Get silence detection kwargs from config."""
        return {
            "threshold_db": self.config.silence.threshold_db,
            "min_duration": self.config.silence.min_duration,
            "padding": self.config.silence.padding,
        }


def quick_process(
    video_path: Path,
    output_path: Path | None = None,
    upload: bool = False,
    generate_clips: bool = False,
) -> PipelineResult:
    """Quick process video with default settings.

    Args:
        video_path: Input video file.
        output_path: Output path (optional).
        upload: Upload to YouTube.
        generate_clips: Generate viral clips.

    Returns:
        Pipeline result.
    """
    pipeline = Pipeline()
    return pipeline.run(video_path, output_path, upload=upload, generate_clips=generate_clips)
