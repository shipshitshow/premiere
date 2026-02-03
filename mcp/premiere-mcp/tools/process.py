"""Processing tools for MCP server."""

from pathlib import Path


async def process_video(
    path: str,
    output: str | None = None,
    steps: list[str] | None = None,
    generate_clips: bool = False,
    max_clips: int = 5,
) -> dict:
    """Process video through the pipeline.

    Args:
        path: Path to input video.
        output: Output path (optional, auto-generated if not provided).
        steps: List of steps to run: silence, audio, video, transcribe, metadata, thumbnail.
               Default: all except clips.
        generate_clips: Whether to generate viral clips.
        max_clips: Maximum number of clips to generate.

    Returns:
        Dict with output_path, transcript_path, clips, metadata, and errors.
    """
    from premiere.pipeline import Pipeline, PipelineStep

    video_path = Path(path)
    output_path = Path(output) if output else None

    # Map step names to PipelineStep enum
    step_map = {
        "silence": PipelineStep.CUT_SILENCE,
        "audio": PipelineStep.ENHANCE_AUDIO,
        "video": PipelineStep.ENHANCE_VIDEO,
        "music": PipelineStep.ADD_MUSIC,
        "transcribe": PipelineStep.TRANSCRIBE,
        "metadata": PipelineStep.GENERATE_METADATA,
        "thumbnail": PipelineStep.GENERATE_THUMBNAIL,
    }

    # Convert step names to PipelineStep
    if steps:
        pipeline_steps = [step_map[s] for s in steps if s in step_map]
    else:
        # Default: all processing steps except clips and upload
        pipeline_steps = [
            PipelineStep.CUT_SILENCE,
            PipelineStep.ENHANCE_AUDIO,
            PipelineStep.ENHANCE_VIDEO,
            PipelineStep.TRANSCRIBE,
            PipelineStep.GENERATE_METADATA,
            PipelineStep.GENERATE_THUMBNAIL,
        ]

    pipeline = Pipeline(steps=pipeline_steps)
    result = pipeline.run(
        video_path,
        output_path,
        generate_clips=generate_clips,
        max_clips=max_clips,
    )

    response = {
        "output_path": str(result.output_path) if result.output_path else None,
        "transcript_path": str(result.transcript_path) if result.transcript_path else None,
        "thumbnail_path": str(result.thumbnail_path) if result.thumbnail_path else None,
        "clips_dir": str(result.clips_dir) if result.clips_dir else None,
        "clips_count": len(result.clips),
        "steps_completed": [s.name for s in result.steps_completed],
        "errors": result.errors,
    }

    if result.metadata:
        response["metadata"] = {
            "titles": result.metadata.titles,
            "description": result.metadata.description[:500] + "..." if len(result.metadata.description) > 500 else result.metadata.description,
            "tags": result.metadata.tags[:10],
            "hashtags": result.metadata.hashtags,
        }

    if result.clips:
        response["clips"] = [
            {
                "path": str(c.path),
                "start": c.start,
                "end": c.end,
                "duration": c.end - c.start,
            }
            for c in result.clips
        ]

    return response


async def cut_silence(
    path: str,
    output: str | None = None,
    threshold_db: float = -40,
    min_duration: float = 0.5,
    padding: float = 0.1,
) -> dict:
    """Remove silence from video.

    Args:
        path: Path to input video.
        output: Output path (optional).
        threshold_db: Silence threshold in dB.
        min_duration: Minimum silence duration in seconds.
        padding: Padding around cuts in seconds.

    Returns:
        Dict with output_path.
    """
    from premiere.processors.silence import cut_silence as cut

    video_path = Path(path)
    output_path = Path(output) if output else video_path.parent / f"{video_path.stem}_no_silence.mp4"

    result = cut(video_path, output_path, threshold_db, min_duration, padding)

    return {
        "output_path": str(result),
    }


async def enhance_audio(path: str, output: str | None = None) -> dict:
    """Enhance audio quality.

    Args:
        path: Path to input video.
        output: Output path (optional).

    Returns:
        Dict with output_path.
    """
    from premiere.processors.audio import enhance_audio as enhance

    video_path = Path(path)
    output_path = Path(output) if output else video_path.parent / f"{video_path.stem}_enhanced_audio.mp4"

    enhance(video_path, output_path)

    return {
        "output_path": str(output_path),
    }


async def transcribe(path: str, output: str | None = None, model: str = "base") -> dict:
    """Transcribe video audio to text.

    Args:
        path: Path to input video.
        output: Output transcript path (optional).
        model: Whisper model size (tiny, base, small, medium, large).

    Returns:
        Dict with transcript text, language, segments, and output path.
    """
    from premiere.generators.transcription import save_transcript, transcribe_video

    video_path = Path(path)
    output_path = Path(output) if output else video_path.parent / f"{video_path.stem}_transcript.md"

    transcript = transcribe_video(video_path, model)
    save_transcript(transcript, output_path, format="md")

    return {
        "output_path": str(output_path),
        "language": transcript.language,
        "segments_count": len(transcript.segments),
        "text_preview": transcript.full_text[:1000] + "..." if len(transcript.full_text) > 1000 else transcript.full_text,
    }
