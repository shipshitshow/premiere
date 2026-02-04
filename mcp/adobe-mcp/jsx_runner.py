"""JSX Runner module for executing ExtendScript files via the proxy server.

This module provides utilities to execute existing ExtendScript (.jsx) files
in Adobe Premiere Pro via the UXP plugin and proxy server connection.
"""

import json
import os
from pathlib import Path
from typing import Any

from adobe_mcp.shared import socket_client


# Default scripts directory
DEFAULT_SCRIPTS_DIR = os.environ.get(
    "SCRIPTS_DIR",
    str(Path(__file__).parent.parent.parent / "scripts")
)


class JSXRunner:
    """Runner for ExtendScript files via the proxy server."""

    def __init__(
        self,
        scripts_dir: str | Path | None = None,
        proxy_url: str = "http://localhost:3001",
        timeout: int = 30
    ):
        """Initialize the JSX runner.

        Args:
            scripts_dir: Directory containing .jsx scripts.
            proxy_url: URL of the proxy server.
            timeout: Command timeout in seconds.
        """
        self.scripts_dir = Path(scripts_dir or DEFAULT_SCRIPTS_DIR)
        self.proxy_url = proxy_url
        self.timeout = timeout

        # Configure socket client
        socket_client.configure(
            app="premiere",
            url=proxy_url,
            timeout=timeout
        )

    def get_script_path(self, script_name: str) -> Path:
        """Get full path to a script file.

        Args:
            script_name: Script filename (with or without .jsx extension).

        Returns:
            Full path to the script.

        Raises:
            FileNotFoundError: If script doesn't exist.
        """
        if not script_name.endswith(".jsx"):
            script_name = f"{script_name}.jsx"

        script_path = self.scripts_dir / script_name
        if not script_path.exists():
            raise FileNotFoundError(f"Script not found: {script_path}")

        return script_path

    def read_script(self, script_name: str) -> str:
        """Read a script file's contents.

        Args:
            script_name: Script filename.

        Returns:
            Script contents as string.
        """
        script_path = self.get_script_path(script_name)
        return script_path.read_text()

    def execute_command(self, action: str, options: dict) -> dict:
        """Execute a command via the proxy server.

        This sends a command to Premiere Pro via the UXP plugin.

        Args:
            action: Command action name.
            options: Command options/parameters.

        Returns:
            Response from Premiere Pro.
        """
        command = {
            "application": "premiere",
            "action": action,
            "options": options
        }

        response = socket_client.send_message_blocking(command)
        return response

    def run_apply_cuts(
        self,
        cuts: list[dict],
        track_index: int = 0
    ) -> dict:
        """Run apply-cuts.jsx with the given cut segments.

        Note: This uses the native UXP API rather than ExtendScript.
        The apply-cuts.jsx script is reference for the cut format.

        Args:
            cuts: List of {start, end} cut segments.
            track_index: Video track index (0-based).

        Returns:
            Result from Premiere Pro.
        """
        # The actual cut logic needs to be implemented in the UXP plugin
        # For now, we return a placeholder that indicates this needs
        # to be implemented in the UXP commands
        return {
            "status": "NOT_IMPLEMENTED",
            "message": "applyCuts action needs to be added to UXP plugin commands/index.js",
            "cuts_count": len(cuts),
            "track_index": track_index
        }

    def run_batch_workflow(
        self,
        workflow_args: dict
    ) -> dict:
        """Run batch-operations.jsx workflow.

        Note: This uses the native UXP API rather than ExtendScript.

        Args:
            workflow_args: Workflow configuration from bridge.create_workflow_args().

        Returns:
            Result from each workflow step.
        """
        results = {
            "steps": [],
            "success": True
        }

        workflow = workflow_args.get("workflow", workflow_args)

        # Step 1: Import media
        if workflow.get("filePaths"):
            try:
                import_result = self.execute_command("importMedia", {
                    "filePaths": workflow["filePaths"]
                })
                results["steps"].append({
                    "step": "import",
                    "result": import_result
                })
            except Exception as e:
                results["steps"].append({
                    "step": "import",
                    "error": str(e)
                })
                results["success"] = False
                return results

        # Step 2: Create sequence from media
        if workflow.get("sequenceName"):
            try:
                # Get the imported item names
                file_names = [
                    Path(p).name for p in workflow.get("filePaths", [])
                ]
                seq_result = self.execute_command("createSequenceFromMedia", {
                    "itemNames": file_names,
                    "sequenceName": workflow["sequenceName"]
                })
                results["steps"].append({
                    "step": "createSequence",
                    "result": seq_result
                })
            except Exception as e:
                results["steps"].append({
                    "step": "createSequence",
                    "error": str(e)
                })

        # Step 3: Apply cuts (needs UXP implementation)
        if workflow.get("cuts"):
            results["steps"].append({
                "step": "cuts",
                "result": {
                    "status": "NOT_IMPLEMENTED",
                    "message": "Cut application via UXP needs implementation",
                    "cuts_count": len(workflow["cuts"])
                }
            })

        # Step 4: Export (needs UXP implementation)
        if workflow.get("outputPath"):
            results["steps"].append({
                "step": "export",
                "result": {
                    "status": "NOT_IMPLEMENTED",
                    "message": "Export via UXP needs implementation",
                    "output_path": workflow["outputPath"]
                }
            })

        return results


def create_runner(
    scripts_dir: str | Path | None = None,
    proxy_url: str = "http://localhost:3001",
    timeout: int = 30
) -> JSXRunner:
    """Create a configured JSX runner instance.

    Args:
        scripts_dir: Directory containing .jsx scripts.
        proxy_url: URL of the proxy server.
        timeout: Command timeout in seconds.

    Returns:
        Configured JSXRunner instance.
    """
    return JSXRunner(
        scripts_dir=scripts_dir,
        proxy_url=proxy_url,
        timeout=timeout
    )


# Convenience functions for direct use

def run_command(action: str, options: dict) -> dict:
    """Execute a single command via the proxy server.

    Args:
        action: Command action name.
        options: Command options/parameters.

    Returns:
        Response from Premiere Pro.
    """
    runner = create_runner()
    return runner.execute_command(action, options)


def import_media(file_paths: list[str]) -> dict:
    """Import media files into Premiere Pro.

    Args:
        file_paths: List of file paths to import.

    Returns:
        Import result.
    """
    return run_command("importMedia", {"filePaths": file_paths})


def create_sequence(item_names: list[str], sequence_name: str = "default") -> dict:
    """Create a sequence from imported media.

    Args:
        item_names: Names of project items to include.
        sequence_name: Name for the new sequence.

    Returns:
        Sequence creation result.
    """
    return run_command("createSequenceFromMedia", {
        "itemNames": item_names,
        "sequenceName": sequence_name
    })


def create_project(directory_path: str, project_name: str) -> dict:
    """Create a new Premiere Pro project.

    Args:
        directory_path: Directory to save the project.
        project_name: Name for the project (without extension).

    Returns:
        Project creation result.
    """
    return run_command("createProject", {
        "path": directory_path,
        "name": project_name
    })


def save_project() -> dict:
    """Save the current project.

    Returns:
        Save result.
    """
    return run_command("saveProject", {})


# ============================================
# EXPORT FUNCTIONS
# ============================================

def export_sequence(sequence_id: str, output_path: str, preset_path: str, use_media_encoder: bool = False) -> dict:
    """Export a sequence to video file.

    Args:
        sequence_id: ID of the sequence to export.
        output_path: Path for the output video file.
        preset_path: Path to the export preset (.epr file).
        use_media_encoder: If True, queue to Media Encoder; if False, export in Premiere.

    Returns:
        Export result.
    """
    return run_command("exportSequence", {
        "sequenceId": sequence_id,
        "outputPath": output_path,
        "presetPath": preset_path,
        "useMediaEncoder": use_media_encoder
    })


def get_export_file_extension(sequence_id: str, preset_path: str) -> dict:
    """Get the file extension for a given export preset.

    Args:
        sequence_id: ID of the sequence.
        preset_path: Path to the export preset.

    Returns:
        Dict with extension.
    """
    return run_command("getExportFileExtension", {
        "sequenceId": sequence_id,
        "presetPath": preset_path
    })


# ============================================
# TRANSCRIPT FUNCTIONS
# ============================================

def import_transcript(project_item_name: str, transcript_json: str) -> dict:
    """Import a transcript to a project item.

    Args:
        project_item_name: Name of the project item.
        transcript_json: Transcript data in Adobe JSON format.

    Returns:
        Import result.
    """
    return run_command("importTranscript", {
        "projectItemName": project_item_name,
        "transcriptJson": transcript_json
    })


def export_transcript(project_item_name: str) -> dict:
    """Export a transcript from a project item.

    Args:
        project_item_name: Name of the project item.

    Returns:
        Dict with transcript JSON.
    """
    return run_command("exportTranscript", {
        "projectItemName": project_item_name
    })


# ============================================
# KEYFRAME FUNCTIONS
# ============================================

def add_keyframe(
    sequence_id: str,
    track_index: int,
    clip_index: int,
    component_index: int,
    param_index: int,
    value: float,
    position_ticks: str,
    is_video: bool = True
) -> dict:
    """Add a keyframe to a clip parameter.

    Args:
        sequence_id: ID of the sequence.
        track_index: Track index.
        clip_index: Clip index on the track.
        component_index: Effect component index.
        param_index: Parameter index within the component.
        value: Keyframe value.
        position_ticks: Position in ticks.
        is_video: True for video track, False for audio.

    Returns:
        Result.
    """
    return run_command("addKeyframe", {
        "sequenceId": sequence_id,
        "trackIndex": track_index,
        "clipIndex": clip_index,
        "componentIndex": component_index,
        "paramIndex": param_index,
        "value": value,
        "positionTicks": position_ticks,
        "isVideo": is_video
    })


def get_keyframes(
    sequence_id: str,
    track_index: int,
    clip_index: int,
    component_index: int,
    param_index: int,
    is_video: bool = True
) -> dict:
    """Get all keyframes for a parameter.

    Args:
        sequence_id: ID of the sequence.
        track_index: Track index.
        clip_index: Clip index on the track.
        component_index: Effect component index.
        param_index: Parameter index.
        is_video: True for video track, False for audio.

    Returns:
        Dict with keyframes list.
    """
    return run_command("getKeyframes", {
        "sequenceId": sequence_id,
        "trackIndex": track_index,
        "clipIndex": clip_index,
        "componentIndex": component_index,
        "paramIndex": param_index,
        "isVideo": is_video
    })


# ============================================
# TRANSITION FUNCTIONS
# ============================================

def get_transition_names() -> dict:
    """Get all available video transition names.

    Returns:
        Dict with list of transition match names.
    """
    return run_command("getTransitionNames", {})


def add_transition_to_start(
    sequence_id: str,
    video_track_index: int,
    track_item_index: int,
    transition_name: str,
    duration: float = None
) -> dict:
    """Add a transition to the start of a clip.

    Args:
        sequence_id: ID of the sequence.
        video_track_index: Video track index.
        track_item_index: Clip index on the track.
        transition_name: Transition match name.
        duration: Optional duration in seconds.

    Returns:
        Result.
    """
    options = {
        "sequenceId": sequence_id,
        "videoTrackIndex": video_track_index,
        "trackItemIndex": track_item_index,
        "transitionName": transition_name
    }
    if duration is not None:
        options["duration"] = duration
    return run_command("addTransitionToStart", options)


def remove_video_transition(
    sequence_id: str,
    video_track_index: int,
    track_item_index: int,
    from_start: bool = True
) -> dict:
    """Remove a video transition from a clip.

    Args:
        sequence_id: ID of the sequence.
        video_track_index: Video track index.
        track_item_index: Clip index on the track.
        from_start: True to remove from start, False from end.

    Returns:
        Result.
    """
    return run_command("removeVideoTransition", {
        "sequenceId": sequence_id,
        "videoTrackIndex": video_track_index,
        "trackItemIndex": track_item_index,
        "fromStart": from_start
    })


# ============================================
# EFFECT FUNCTIONS
# ============================================

def get_effect_names() -> dict:
    """Get all available video effect names.

    Returns:
        Dict with list of effect match names.
    """
    return run_command("getEffectNames", {})


def get_audio_effect_names() -> dict:
    """Get all available audio effect names.

    Returns:
        Dict with list of effect match names.
    """
    return run_command("getAudioEffectNames", {})


def add_video_effect(
    sequence_id: str,
    video_track_index: int,
    track_item_index: int,
    effect_match_name: str,
    insert_index: int = 2
) -> dict:
    """Add a video effect to a clip.

    Args:
        sequence_id: ID of the sequence.
        video_track_index: Video track index.
        track_item_index: Clip index on the track.
        effect_match_name: Effect match name.
        insert_index: Position to insert the effect.

    Returns:
        Result.
    """
    return run_command("addVideoEffect", {
        "sequenceId": sequence_id,
        "videoTrackIndex": video_track_index,
        "trackItemIndex": track_item_index,
        "effectMatchName": effect_match_name,
        "insertIndex": insert_index
    })


def add_audio_effect(
    sequence_id: str,
    audio_track_index: int,
    track_item_index: int,
    effect_name: str,
    insert_index: int = 2
) -> dict:
    """Add an audio effect to a clip.

    Args:
        sequence_id: ID of the sequence.
        audio_track_index: Audio track index.
        track_item_index: Clip index on the track.
        effect_name: Effect display name.
        insert_index: Position to insert the effect.

    Returns:
        Result.
    """
    return run_command("addAudioEffect", {
        "sequenceId": sequence_id,
        "audioTrackIndex": audio_track_index,
        "trackItemIndex": track_item_index,
        "effectName": effect_name,
        "insertIndex": insert_index
    })


def remove_effect(
    sequence_id: str,
    track_index: int,
    clip_index: int,
    component_index: int,
    is_video: bool = True
) -> dict:
    """Remove an effect from a clip.

    Args:
        sequence_id: ID of the sequence.
        track_index: Track index.
        clip_index: Clip index on the track.
        component_index: Effect component index to remove.
        is_video: True for video track, False for audio.

    Returns:
        Result.
    """
    return run_command("removeEffect", {
        "sequenceId": sequence_id,
        "trackIndex": track_index,
        "clipIndex": clip_index,
        "componentIndex": component_index,
        "isVideo": is_video
    })


def get_clip_effects(
    sequence_id: str,
    track_index: int,
    clip_index: int,
    is_video: bool = True
) -> dict:
    """Get all effects on a clip.

    Args:
        sequence_id: ID of the sequence.
        track_index: Track index.
        clip_index: Clip index on the track.
        is_video: True for video track, False for audio.

    Returns:
        Dict with effects list.
    """
    return run_command("getClipEffects", {
        "sequenceId": sequence_id,
        "trackIndex": track_index,
        "clipIndex": clip_index,
        "isVideo": is_video
    })


# ============================================
# SEQUENCE FUNCTIONS
# ============================================

def set_sequence_in_out_points(
    sequence_id: str,
    in_point_ticks: str,
    out_point_ticks: str
) -> dict:
    """Set sequence in and out points (work area).

    Args:
        sequence_id: ID of the sequence.
        in_point_ticks: In point in ticks.
        out_point_ticks: Out point in ticks.

    Returns:
        Result.
    """
    return run_command("setSequenceInOutPoints", {
        "sequenceId": sequence_id,
        "inPointTicks": in_point_ticks,
        "outPointTicks": out_point_ticks
    })


def clear_sequence_in_out_points(sequence_id: str) -> dict:
    """Clear sequence in and out points.

    Args:
        sequence_id: ID of the sequence.

    Returns:
        Result.
    """
    return run_command("clearSequenceInOutPoints", {
        "sequenceId": sequence_id
    })


def create_subsequence(sequence_id: str, ignore_track_targeting: bool = True) -> dict:
    """Create a subsequence from the current sequence.

    Args:
        sequence_id: ID of the sequence.
        ignore_track_targeting: Whether to ignore track targeting.

    Returns:
        Dict with new subsequence info.
    """
    return run_command("createSubsequence", {
        "sequenceId": sequence_id,
        "ignoreTrackTargeting": ignore_track_targeting
    })


def add_handles_to_clip(
    sequence_id: str,
    track_index: int,
    clip_index: int,
    in_point_frames: int = 0,
    out_point_frames: int = 0,
    is_video: bool = True
) -> dict:
    """Add handles (extra frames) to a clip.

    Args:
        sequence_id: ID of the sequence.
        track_index: Track index.
        clip_index: Clip index on the track.
        in_point_frames: Frames to add at start.
        out_point_frames: Frames to add at end.
        is_video: True for video track, False for audio.

    Returns:
        Result.
    """
    return run_command("addHandlesToClip", {
        "sequenceId": sequence_id,
        "trackIndex": track_index,
        "clipIndex": clip_index,
        "inPointFrames": in_point_frames,
        "outPointFrames": out_point_frames,
        "isVideo": is_video
    })


def create_empty_sequence(sequence_name: str) -> dict:
    """Create an empty sequence.

    Args:
        sequence_name: Name for the new sequence.

    Returns:
        Dict with new sequence info.
    """
    return run_command("createSequence", {
        "sequenceName": sequence_name
    })


# ============================================
# SELECTION FUNCTIONS
# ============================================

def get_sequence_selection(sequence_id: str) -> dict:
    """Get the current selection in a sequence.

    Args:
        sequence_id: ID of the sequence.

    Returns:
        Dict with selected items.
    """
    return run_command("getSequenceSelection", {
        "sequenceId": sequence_id
    })


def set_sequence_selection(
    sequence_id: str,
    video_items: list = None,
    audio_items: list = None
) -> dict:
    """Set the selection in a sequence.

    Args:
        sequence_id: ID of the sequence.
        video_items: List of {trackIndex, clipIndex} for video.
        audio_items: List of {trackIndex, clipIndex} for audio.

    Returns:
        Result.
    """
    return run_command("setSequenceSelection", {
        "sequenceId": sequence_id,
        "videoItems": video_items or [],
        "audioItems": audio_items or []
    })


# ============================================
# MOGRT FUNCTIONS
# ============================================

def insert_mogrt(
    sequence_id: str,
    mogrt_path: str,
    insert_time_ticks: str = None,
    video_track_index: int = 0,
    audio_track_index: int = 0
) -> dict:
    """Insert a Motion Graphics Template (MOGRT).

    Args:
        sequence_id: ID of the sequence.
        mogrt_path: Path to the .mogrt file.
        insert_time_ticks: Optional insertion time in ticks.
        video_track_index: Video track index.
        audio_track_index: Audio track index.

    Returns:
        Result.
    """
    options = {
        "sequenceId": sequence_id,
        "mogrtPath": mogrt_path,
        "videoTrackIndex": video_track_index,
        "audioTrackIndex": audio_track_index
    }
    if insert_time_ticks:
        options["insertTimeTicks"] = insert_time_ticks
    return run_command("insertMogrt", options)
