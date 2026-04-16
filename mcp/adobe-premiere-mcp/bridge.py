"""Bridge module to convert Python pipeline output to Premiere format.

This module provides utilities to convert silence detection segments from
the Python pipeline (`premiere-python-mcp`) to the format expected by Adobe Premiere
ExtendScript files (apply-cuts.jsx).
"""

import json
from pathlib import Path
from typing import TypedDict


class CutSegment(TypedDict):
    """A segment to cut (silence segment to remove)."""
    start: float
    end: float


class AudioSegment(TypedDict):
    """An audio segment to keep (speech segment)."""
    start: float
    end: float
    duration: float


class SegmentsData(TypedDict):
    """Structure of segments.json from Python pipeline."""
    silence_segments: list[dict]
    audio_segments: list[dict]
    video_duration: float
    stats: dict


def load_segments(segments_path: str | Path) -> SegmentsData:
    """Load segments.json from the Python pipeline.

    Args:
        segments_path: Path to segments.json file.

    Returns:
        Parsed segments data.

    Raises:
        FileNotFoundError: If segments file doesn't exist.
        json.JSONDecodeError: If file is not valid JSON.
    """
    path = Path(segments_path)
    with open(path) as f:
        return json.load(f)


def segments_to_premiere_cuts(segments_path: str | Path) -> list[CutSegment]:
    """Convert Python pipeline segments to Premiere cut format.

    Loads segments.json and returns silence segments in the format
    expected by apply-cuts.jsx: [{start, end}, ...]

    Args:
        segments_path: Path to segments.json file.

    Returns:
        List of cut segments (silence segments to remove).
    """
    data = load_segments(segments_path)

    cuts = []
    for segment in data.get("silence_segments", []):
        cuts.append({
            "start": segment["start"],
            "end": segment["end"]
        })

    return cuts


def segments_to_keep_ranges(segments_path: str | Path) -> list[AudioSegment]:
    """Get segments to keep (audio/speech segments).

    Args:
        segments_path: Path to segments.json file.

    Returns:
        List of audio segments to preserve.
    """
    data = load_segments(segments_path)

    segments = []
    for segment in data.get("audio_segments", []):
        segments.append({
            "start": segment["start"],
            "end": segment["end"],
            "duration": segment["end"] - segment["start"]
        })

    return segments


def create_jsx_args(
    segments_path: str | Path,
    track_index: int = 0
) -> dict:
    """Create arguments for apply-cuts.jsx.

    Args:
        segments_path: Path to segments.json file.
        track_index: Video track index (0-based).

    Returns:
        Dict ready to be JSON serialized and passed to apply-cuts.jsx.
    """
    cuts = segments_to_premiere_cuts(segments_path)

    return {
        "cuts": cuts,
        "trackIndex": track_index
    }


def create_workflow_args(
    video_path: str | Path,
    segments_path: str | Path,
    output_path: str | Path,
    sequence_name: str | None = None,
    preset: str = "Match Source - High bitrate"
) -> dict:
    """Create arguments for batch-operations.jsx runFullWorkflow.

    Args:
        video_path: Path to source video file.
        segments_path: Path to segments.json file.
        output_path: Path for exported video.
        sequence_name: Name for the sequence (defaults to video filename).
        preset: Export preset name.

    Returns:
        Dict ready for batch-operations.jsx fullWorkflow action.
    """
    video_path = Path(video_path)
    output_path = Path(output_path)

    cuts = segments_to_premiere_cuts(segments_path)

    return {
        "action": "fullWorkflow",
        "workflow": {
            "filePaths": [str(video_path.absolute())],
            "sequenceName": sequence_name or video_path.stem,
            "cuts": cuts,
            "outputPath": str(output_path.absolute()),
            "preset": preset
        }
    }


def get_segment_stats(segments_path: str | Path) -> dict:
    """Get statistics about the segments.

    Args:
        segments_path: Path to segments.json file.

    Returns:
        Dict with statistics including:
        - total_duration: Original video duration
        - silence_duration: Total silence time
        - audio_duration: Total audio time
        - silence_count: Number of silence segments
        - audio_count: Number of audio segments
        - silence_percentage: Percentage of video that is silence
    """
    data = load_segments(segments_path)

    silence_duration = sum(
        s["end"] - s["start"]
        for s in data.get("silence_segments", [])
    )
    audio_duration = sum(
        s["end"] - s["start"]
        for s in data.get("audio_segments", [])
    )
    total_duration = data.get("video_duration", silence_duration + audio_duration)

    return {
        "total_duration": total_duration,
        "silence_duration": silence_duration,
        "audio_duration": audio_duration,
        "silence_count": len(data.get("silence_segments", [])),
        "audio_count": len(data.get("audio_segments", [])),
        "silence_percentage": (silence_duration / total_duration * 100) if total_duration > 0 else 0,
        "estimated_output_duration": audio_duration
    }


def validate_segments(segments_path: str | Path) -> dict:
    """Validate segments data for consistency.

    Args:
        segments_path: Path to segments.json file.

    Returns:
        Dict with validation results:
        - valid: True if segments are valid
        - errors: List of error messages
        - warnings: List of warning messages
    """
    data = load_segments(segments_path)

    errors = []
    warnings = []

    # Check required fields
    if "silence_segments" not in data:
        errors.append("Missing 'silence_segments' field")
    if "audio_segments" not in data:
        errors.append("Missing 'audio_segments' field")
    if "video_duration" not in data:
        warnings.append("Missing 'video_duration' field")

    # Validate segment structure
    for i, seg in enumerate(data.get("silence_segments", [])):
        if "start" not in seg or "end" not in seg:
            errors.append(f"Silence segment {i} missing start/end")
        elif seg["start"] >= seg["end"]:
            errors.append(f"Silence segment {i} has invalid range: {seg['start']} >= {seg['end']}")

    for i, seg in enumerate(data.get("audio_segments", [])):
        if "start" not in seg or "end" not in seg:
            errors.append(f"Audio segment {i} missing start/end")
        elif seg["start"] >= seg["end"]:
            errors.append(f"Audio segment {i} has invalid range: {seg['start']} >= {seg['end']}")

    # Check for overlapping segments
    silence = sorted(data.get("silence_segments", []), key=lambda x: x.get("start", 0))
    for i in range(len(silence) - 1):
        if silence[i].get("end", 0) > silence[i + 1].get("start", 0):
            warnings.append(f"Overlapping silence segments at index {i} and {i + 1}")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }
