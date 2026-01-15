"""Video transcription using Whisper."""

import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from premiere.utils.config import get_config, get_temp_dir
from premiere.utils.ffmpeg import extract_audio
from premiere.utils.logger import get_logger


@dataclass
class TranscriptSegment:
    """A segment of transcribed text."""

    start: float
    end: float
    text: str


@dataclass
class Transcript:
    """Full video transcript."""

    segments: list[TranscriptSegment]
    full_text: str
    language: str


def transcribe_video(
    video_path: Path,
    model_size: str | None = None,
) -> Transcript:
    """Transcribe video audio using Whisper.

    Args:
        video_path: Path to video file.
        model_size: Whisper model size (tiny, base, small, medium, large).

    Returns:
        Transcript with segments and full text.
    """
    logger = get_logger()
    config = get_config().ai
    model = model_size or config.transcription_model

    logger.info(f"Transcribing {video_path.name} with whisper-{model}")

    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise ImportError(
            "faster-whisper not installed. Run: pip install faster-whisper"
        ) from e

    # Extract audio to workspace temp file
    temp_base = get_temp_dir()
    temp_path = temp_base / f"transcribe_{int(time.time())}"
    temp_path.mkdir(parents=True, exist_ok=True)
    audio_path = temp_path / "audio.wav"
    
    try:
        extract_audio(video_path, audio_path)

        # Load model and transcribe
        whisper_model = WhisperModel(
            model,
            device="auto",
            compute_type="auto",
        )

        segments_generator, info = whisper_model.transcribe(
            str(audio_path),
            beam_size=5,
            vad_filter=True,
        )

        # Collect segments
        segments = []
        texts = []
        for segment in segments_generator:
            segments.append(TranscriptSegment(
                start=segment.start,
                end=segment.end,
                text=segment.text.strip(),
            ))
            texts.append(segment.text.strip())
    finally:
        # Clean up temp directory
        if temp_path.exists():
            shutil.rmtree(temp_path, ignore_errors=True)

    full_text = " ".join(texts)
    logger.info(f"Transcription complete: {len(segments)} segments, {len(full_text)} chars")

    return Transcript(
        segments=segments,
        full_text=full_text,
        language=info.language,
    )


def generate_srt(transcript: Transcript, output_path: Path) -> Path:
    """Generate SRT subtitle file from transcript.

    Args:
        transcript: Video transcript.
        output_path: Path for output SRT file.

    Returns:
        Path to generated SRT file.
    """
    logger = get_logger()

    def format_timestamp(seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    lines = []
    for i, segment in enumerate(transcript.segments, 1):
        lines.append(str(i))
        lines.append(f"{format_timestamp(segment.start)} --> {format_timestamp(segment.end)}")
        lines.append(segment.text)
        lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info(f"Generated SRT: {output_path}")
    return output_path


def generate_chapters(transcript: Transcript, min_gap: float = 30.0) -> list[dict]:
    """Generate chapter markers from transcript.

    Args:
        transcript: Video transcript.
        min_gap: Minimum gap between chapters in seconds.

    Returns:
        List of chapter dicts with 'time' and 'title' keys.
    """
    if not transcript.segments:
        return []

    chapters = []
    last_chapter_time = -min_gap

    for segment in transcript.segments:
        # Create chapter at significant gaps
        if segment.start - last_chapter_time >= min_gap:
            # Use first few words as chapter title
            words = segment.text.split()[:5]
            title = " ".join(words)
            if len(title) > 30:
                title = title[:27] + "..."

            chapters.append({
                "time": segment.start,
                "title": title,
            })
            last_chapter_time = segment.start

    return chapters


def save_transcript(
    transcript: Transcript,
    output_path: Path,
    format: str = "md",
) -> Path:
    """Save transcript to file.

    Args:
        transcript: Video transcript.
        output_path: Output file path.
        format: Output format (md, txt, json).

    Returns:
        Path to saved file.
    """
    import json

    logger = get_logger()

    if format == "json":
        data = {
            "language": transcript.language,
            "full_text": transcript.full_text,
            "segments": [
                {
                    "start": seg.start,
                    "end": seg.end,
                    "text": seg.text,
                }
                for seg in transcript.segments
            ],
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    elif format == "md":
        lines = [
            f"# Transcript",
            f"",
            f"**Language:** {transcript.language}",
            f"**Segments:** {len(transcript.segments)}",
            f"",
            f"## Full Text",
            f"",
            transcript.full_text,
            f"",
            f"## Timestamped Segments",
            f"",
        ]
        for seg in transcript.segments:
            timestamp = _format_timestamp_simple(seg.start)
            lines.append(f"**[{timestamp}]** {seg.text}")
            lines.append("")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    else:  # txt
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(transcript.full_text)

    logger.info(f"Saved transcript: {output_path}")
    return output_path


def _format_timestamp_simple(seconds: float) -> str:
    """Format seconds as MM:SS or HH:MM:SS."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"
