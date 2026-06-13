"""Premiere UXP command helpers.

The MCP server talks to the Premiere UXP plugin through the local proxy. These
helpers expose the lower-level UXP command names used by the plugin.
"""

import os

from adobe_mcp.shared import socket_client


PROXY_URL = os.environ.get("PROXY_URL", "http://localhost:3001")
PROXY_TIMEOUT = int(os.environ.get("PROXY_TIMEOUT", "120"))

_configured = False


def _ensure_configured() -> None:
    global _configured

    if _configured:
        return

    socket_client.configure(app="premiere", url=PROXY_URL, timeout=PROXY_TIMEOUT)
    _configured = True


def run_command(action: str, options: dict) -> dict:
    """Execute a Premiere UXP command through the proxy server."""
    _ensure_configured()
    return socket_client.send_message_blocking(
        {
            "application": "premiere",
            "action": action,
            "options": options,
        }
    )


def export_sequence(
    sequence_id: str,
    output_path: str,
    preset_path: str,
    use_media_encoder: bool = False,
) -> dict:
    """Export a sequence using Premiere or Adobe Media Encoder."""
    return run_command(
        "exportSequence",
        {
            "sequenceId": sequence_id,
            "outputPath": output_path,
            "presetPath": preset_path,
            "useMediaEncoder": use_media_encoder,
        },
    )


def get_export_file_extension(sequence_id: str, preset_path: str) -> dict:
    """Get the file extension Premiere will produce for an export preset."""
    return run_command(
        "getExportFileExtension",
        {
            "sequenceId": sequence_id,
            "presetPath": preset_path,
        },
    )


def import_transcript(project_item_name: str, transcript_json: str) -> dict:
    """Import transcript JSON into a project item."""
    return run_command(
        "importTranscript",
        {
            "projectItemName": project_item_name,
            "transcriptJson": transcript_json,
        },
    )


def export_transcript(project_item_name: str) -> dict:
    """Export transcript JSON from a project item."""
    return run_command(
        "exportTranscript",
        {
            "projectItemName": project_item_name,
        },
    )


def add_keyframe(
    sequence_id: str,
    track_index: int,
    clip_index: int,
    component_index: int,
    param_index: int,
    value: float,
    position_ticks: str,
    is_video: bool = True,
) -> dict:
    """Add a keyframe to a clip component parameter."""
    return run_command(
        "addKeyframe",
        {
            "sequenceId": sequence_id,
            "trackIndex": track_index,
            "clipIndex": clip_index,
            "componentIndex": component_index,
            "paramIndex": param_index,
            "value": value,
            "positionTicks": position_ticks,
            "isVideo": is_video,
        },
    )


def get_keyframes(
    sequence_id: str,
    track_index: int,
    clip_index: int,
    component_index: int,
    param_index: int,
    is_video: bool = True,
) -> dict:
    """Get keyframes for a clip component parameter."""
    return run_command(
        "getKeyframes",
        {
            "sequenceId": sequence_id,
            "trackIndex": track_index,
            "clipIndex": clip_index,
            "componentIndex": component_index,
            "paramIndex": param_index,
            "isVideo": is_video,
        },
    )


def get_transition_names() -> dict:
    """Get available video transition names."""
    return run_command("getTransitionNames", {})


def add_transition_to_start(
    sequence_id: str,
    video_track_index: int,
    track_item_index: int,
    transition_name: str,
    duration: float | None = None,
) -> dict:
    """Add a video transition to the start of a clip."""
    options = {
        "sequenceId": sequence_id,
        "videoTrackIndex": video_track_index,
        "trackItemIndex": track_item_index,
        "transitionName": transition_name,
    }
    if duration is not None:
        options["duration"] = duration
    return run_command("addTransitionToStart", options)


def remove_video_transition(
    sequence_id: str,
    video_track_index: int,
    track_item_index: int,
    from_start: bool = True,
) -> dict:
    """Remove a video transition from a clip."""
    return run_command(
        "removeVideoTransition",
        {
            "sequenceId": sequence_id,
            "videoTrackIndex": video_track_index,
            "trackItemIndex": track_item_index,
            "fromStart": from_start,
        },
    )


def get_effect_names() -> dict:
    """Get available video effect names."""
    return run_command("getEffectNames", {})


def get_audio_effect_names() -> dict:
    """Get available audio effect names."""
    return run_command("getAudioEffectNames", {})


def add_video_effect(
    sequence_id: str,
    video_track_index: int,
    track_item_index: int,
    effect_match_name: str,
    insert_index: int = 2,
) -> dict:
    """Add a video effect to a clip."""
    return run_command(
        "addVideoEffect",
        {
            "sequenceId": sequence_id,
            "videoTrackIndex": video_track_index,
            "trackItemIndex": track_item_index,
            "effectMatchName": effect_match_name,
            "insertIndex": insert_index,
        },
    )


def add_audio_effect(
    sequence_id: str,
    audio_track_index: int,
    track_item_index: int,
    effect_name: str,
    insert_index: int = 2,
) -> dict:
    """Add an audio effect to a clip."""
    return run_command(
        "addAudioEffect",
        {
            "sequenceId": sequence_id,
            "audioTrackIndex": audio_track_index,
            "trackItemIndex": track_item_index,
            "effectName": effect_name,
            "insertIndex": insert_index,
        },
    )


def remove_effect(
    sequence_id: str,
    track_index: int,
    clip_index: int,
    component_index: int,
    is_video: bool = True,
) -> dict:
    """Remove an effect from a clip."""
    return run_command(
        "removeEffect",
        {
            "sequenceId": sequence_id,
            "trackIndex": track_index,
            "clipIndex": clip_index,
            "componentIndex": component_index,
            "isVideo": is_video,
        },
    )


def get_clip_effects(
    sequence_id: str,
    track_index: int,
    clip_index: int,
    is_video: bool = True,
) -> dict:
    """Get effects on a clip."""
    return run_command(
        "getClipEffects",
        {
            "sequenceId": sequence_id,
            "trackIndex": track_index,
            "clipIndex": clip_index,
            "isVideo": is_video,
        },
    )


def set_sequence_in_out_points(
    sequence_id: str,
    in_point_ticks: str,
    out_point_ticks: str,
) -> dict:
    """Set sequence in and out points."""
    return run_command(
        "setSequenceInOutPoints",
        {
            "sequenceId": sequence_id,
            "inPointTicks": in_point_ticks,
            "outPointTicks": out_point_ticks,
        },
    )


def clear_sequence_in_out_points(sequence_id: str) -> dict:
    """Clear sequence in and out points."""
    return run_command(
        "clearSequenceInOutPoints",
        {
            "sequenceId": sequence_id,
        },
    )


def create_subsequence(
    sequence_id: str,
    ignore_track_targeting: bool = True,
) -> dict:
    """Create a subsequence from the current sequence."""
    return run_command(
        "createSubsequence",
        {
            "sequenceId": sequence_id,
            "ignoreTrackTargeting": ignore_track_targeting,
        },
    )


def add_handles_to_clip(
    sequence_id: str,
    track_index: int,
    clip_index: int,
    in_point_frames: int = 0,
    out_point_frames: int = 0,
    is_video: bool = True,
) -> dict:
    """Add handles to a clip."""
    return run_command(
        "addHandlesToClip",
        {
            "sequenceId": sequence_id,
            "trackIndex": track_index,
            "clipIndex": clip_index,
            "inPointFrames": in_point_frames,
            "outPointFrames": out_point_frames,
            "isVideo": is_video,
        },
    )


def create_empty_sequence(sequence_name: str) -> dict:
    """Create an empty sequence."""
    return run_command(
        "createSequence",
        {
            "sequenceName": sequence_name,
        },
    )


def get_sequence_selection(sequence_id: str) -> dict:
    """Get the current sequence selection."""
    return run_command(
        "getSequenceSelection",
        {
            "sequenceId": sequence_id,
        },
    )


def set_sequence_selection(
    sequence_id: str,
    video_items: list | None = None,
    audio_items: list | None = None,
) -> dict:
    """Set the current sequence selection."""
    return run_command(
        "setSequenceSelection",
        {
            "sequenceId": sequence_id,
            "videoItems": video_items or [],
            "audioItems": audio_items or [],
        },
    )


def insert_mogrt(
    sequence_id: str,
    mogrt_path: str,
    insert_time_ticks: str | None = None,
    video_track_index: int = 0,
    audio_track_index: int = 0,
) -> dict:
    """Insert a Motion Graphics Template into the sequence."""
    options = {
        "sequenceId": sequence_id,
        "mogrtPath": mogrt_path,
        "videoTrackIndex": video_track_index,
        "audioTrackIndex": audio_track_index,
    }
    if insert_time_ticks:
        options["insertTimeTicks"] = insert_time_ticks
    return run_command("insertMogrt", options)
