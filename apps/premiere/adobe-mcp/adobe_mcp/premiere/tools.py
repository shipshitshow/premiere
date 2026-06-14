"""Additional Premiere MCP tools backed by the UXP plugin.

The core server owns timeline inspection, trim, delete, and transcript-removal
operations. This module adds direct wrappers for UXP commands that are useful
for finishing work inside Premiere.
"""

from mcp.server.fastmcp import FastMCP

from .command_runner import (
    add_audio_effect,
    add_effect_with_params,
    add_handles_to_clip,
    add_keyframe,
    add_transition_to_start,
    add_video_effect,
    clear_sequence_in_out_points,
    create_empty_sequence,
    create_subsequence,
    export_sequence,
    export_transcript,
    get_audio_effect_names,
    get_clip_effects,
    get_effect_names,
    get_export_file_extension,
    get_keyframes,
    get_sequence_layout,
    get_sequence_selection,
    get_transition_names,
    import_transcript,
    insert_mogrt,
    remove_effect,
    remove_video_transition,
    run_command,
    set_sequence_in_out_points,
    set_sequence_selection,
)


# Lumetri Color effect match name (stable across recent Premiere versions).
LUMETRI_MATCH_NAME = "AE.ADBE Lumetri"

# Default audio-cleanup effect labels matched (case-insensitively, by substring)
# against the live display names from getAudioEffectNames.
DEFAULT_AUDIO_CLEANUP = ["DeNoise", "DeReverb"]


def _unwrap(response: dict) -> dict:
    """Pull the plugin payload out of a {response, status} proxy envelope."""
    if isinstance(response, dict):
        return response.get("response", response) or {}
    return {}


def register_tools(mcp: FastMCP) -> None:
    """Register additional Premiere-only MCP tools."""

    @mcp.tool()
    def premiere_export_sequence(
        sequence_id: str,
        output_path: str,
        preset_path: str,
        use_media_encoder: bool = False,
    ) -> dict:
        """Export a Premiere Pro sequence to a video file."""
        return export_sequence(sequence_id, output_path, preset_path, use_media_encoder)

    @mcp.tool()
    def premiere_get_export_extension(sequence_id: str, preset_path: str) -> dict:
        """Get the file extension that will be used for an export preset."""
        return get_export_file_extension(sequence_id, preset_path)

    @mcp.tool()
    def premiere_import_transcript(project_item_name: str, transcript_json: str) -> dict:
        """Import transcript JSON into a Premiere project item."""
        return import_transcript(project_item_name, transcript_json)

    @mcp.tool()
    def premiere_export_transcript(project_item_name: str) -> dict:
        """Export transcript JSON from a Premiere project item."""
        return export_transcript(project_item_name)

    @mcp.tool()
    def premiere_add_keyframe(
        sequence_id: str,
        track_index: int,
        clip_index: int,
        component_index: int,
        param_index: int,
        value: float,
        position_ticks: str,
        is_video: bool = True,
    ) -> dict:
        """Add a keyframe to an effect parameter on a clip."""
        return add_keyframe(
            sequence_id,
            track_index,
            clip_index,
            component_index,
            param_index,
            value,
            position_ticks,
            is_video,
        )

    @mcp.tool()
    def premiere_get_keyframes(
        sequence_id: str,
        track_index: int,
        clip_index: int,
        component_index: int,
        param_index: int,
        is_video: bool = True,
    ) -> dict:
        """Get all keyframes for an effect parameter on a clip."""
        return get_keyframes(
            sequence_id,
            track_index,
            clip_index,
            component_index,
            param_index,
            is_video,
        )

    @mcp.tool()
    def premiere_get_transitions() -> dict:
        """Get available video transition names."""
        return get_transition_names()

    @mcp.tool()
    def premiere_add_transition(
        sequence_id: str,
        video_track_index: int,
        track_item_index: int,
        transition_name: str,
        duration: float | None = None,
        at_start: bool = True,
    ) -> dict:
        """Add a video transition to a clip."""
        if at_start:
            return add_transition_to_start(
                sequence_id,
                video_track_index,
                track_item_index,
                transition_name,
                duration,
            )

        return run_command(
            "appendVideoTransition",
            {
                "sequenceId": sequence_id,
                "videoTrackIndex": video_track_index,
                "trackItemIndex": track_item_index,
                "transitionName": transition_name,
                "duration": duration or 1.0,
                "clipAlignment": 0,
            },
        )

    @mcp.tool()
    def premiere_remove_transition(
        sequence_id: str,
        video_track_index: int,
        track_item_index: int,
        from_start: bool = True,
    ) -> dict:
        """Remove a video transition from a clip."""
        return remove_video_transition(
            sequence_id,
            video_track_index,
            track_item_index,
            from_start,
        )

    @mcp.tool()
    def premiere_get_video_effects() -> dict:
        """Get available video effect names."""
        return get_effect_names()

    @mcp.tool()
    def premiere_get_audio_effects() -> dict:
        """Get available audio effect names."""
        return get_audio_effect_names()

    @mcp.tool()
    def premiere_add_effect(
        sequence_id: str,
        track_index: int,
        clip_index: int,
        effect_name: str,
        is_video: bool = True,
        insert_index: int = 2,
    ) -> dict:
        """Add an audio or video effect to a clip."""
        if is_video:
            return add_video_effect(
                sequence_id,
                track_index,
                clip_index,
                effect_name,
                insert_index,
            )

        return add_audio_effect(
            sequence_id,
            track_index,
            clip_index,
            effect_name,
            insert_index,
        )

    @mcp.tool()
    def premiere_remove_effect(
        sequence_id: str,
        track_index: int,
        clip_index: int,
        component_index: int,
        is_video: bool = True,
    ) -> dict:
        """Remove an effect from a clip."""
        return remove_effect(
            sequence_id,
            track_index,
            clip_index,
            component_index,
            is_video,
        )

    @mcp.tool()
    def premiere_get_clip_effects(
        sequence_id: str,
        track_index: int,
        clip_index: int,
        is_video: bool = True,
    ) -> dict:
        """Get all effects applied to a clip."""
        return get_clip_effects(sequence_id, track_index, clip_index, is_video)

    @mcp.tool()
    def premiere_set_work_area(
        sequence_id: str,
        in_point_ticks: str,
        out_point_ticks: str,
    ) -> dict:
        """Set the sequence in/out points."""
        return set_sequence_in_out_points(sequence_id, in_point_ticks, out_point_ticks)

    @mcp.tool()
    def premiere_clear_work_area(sequence_id: str) -> dict:
        """Clear the sequence in/out points."""
        return clear_sequence_in_out_points(sequence_id)

    @mcp.tool()
    def premiere_create_subsequence(
        sequence_id: str,
        ignore_track_targeting: bool = True,
    ) -> dict:
        """Create a subsequence from the current sequence."""
        return create_subsequence(sequence_id, ignore_track_targeting)

    @mcp.tool()
    def premiere_add_handles(
        sequence_id: str,
        track_index: int,
        clip_index: int,
        in_frames: int = 0,
        out_frames: int = 0,
        is_video: bool = True,
    ) -> dict:
        """Add handles to a clip."""
        return add_handles_to_clip(
            sequence_id,
            track_index,
            clip_index,
            in_frames,
            out_frames,
            is_video,
        )

    @mcp.tool()
    def premiere_create_sequence(sequence_name: str) -> dict:
        """Create a new empty sequence."""
        return create_empty_sequence(sequence_name)

    @mcp.tool()
    def premiere_get_selection(sequence_id: str) -> dict:
        """Get the current clip selection in a sequence."""
        return get_sequence_selection(sequence_id)

    @mcp.tool()
    def premiere_set_selection(
        sequence_id: str,
        video_items: list | None = None,
        audio_items: list | None = None,
    ) -> dict:
        """Set the current clip selection in a sequence."""
        return set_sequence_selection(sequence_id, video_items, audio_items)

    @mcp.tool()
    def premiere_insert_mogrt(
        sequence_id: str,
        mogrt_path: str,
        insert_time_ticks: str | None = None,
        video_track_index: int = 0,
        audio_track_index: int = 0,
    ) -> dict:
        """Insert a Motion Graphics Template into a sequence."""
        return insert_mogrt(
            sequence_id,
            mogrt_path,
            insert_time_ticks,
            video_track_index,
            audio_track_index,
        )

    @mcp.tool()
    def premiere_get_sequence_layout(sequence_id: str) -> dict:
        """Get one sequence's clip layout (video/audio track items + frame rate).

        Lighter than premiere_get_full_project_data, which walks every sequence.
        Returns {id, name, frameRateValue, ticksPerFrame, videoTracks,
        audioTracks}. Use this to inspect clip boundaries, count clips, or read
        the frame rate before an edit. For POST-CUT verification prefer
        verify_sequence_layout, which also reports residual gaps and
        video/audio end-sync from this same data.
        """
        return get_sequence_layout(sequence_id)

    @mcp.tool()
    def premiere_apply_lumetri_correction(
        sequence_id: str,
        video_track_index: int,
        track_item_index: int,
        properties: list | None = None,
    ) -> dict:
        """Apply a Lumetri Color effect to ONE video clip and set its parameters.

        This is UXP-scriptable color correction. ``properties`` is a list of
        {"name": "<Lumetri param display name>", "value": <number>} entries.
        Unknown parameter names are SKIPPED (not errored); the response lists
        ``availableParams`` so you can discover the exact names for this Premiere
        version, then re-call with the correct ones. Pass an empty list to just
        add the effect and read back its available params.

        Limitation: this sets the parameters you pass explicitly. It does NOT
        press the Lumetri panel's "Auto" button — there is no UXP API for that.
        To auto-balance a clip, open the Lumetri Color panel in Premiere and
        click Auto manually.
        """
        result = add_effect_with_params(
            sequence_id,
            video_track_index,
            track_item_index,
            LUMETRI_MATCH_NAME,
            properties,
        )
        return _unwrap(result)

    @mcp.tool()
    def premiere_clean_audio_pipeline(
        sequence_id: str,
        effect_labels: list | None = None,
        audio_track_index: int | None = None,
    ) -> dict:
        """Apply audio-cleanup effects (DeNoise/DeReverb) across audio clips.

        Fuzzy-matches ``effect_labels`` (default ["DeNoise", "DeReverb"]) against
        the live display names from getAudioEffectNames, then adds each matched
        effect to every audio clip in the sequence (or only the clips on
        ``audio_track_index`` if given). Audio effects are non-destructive and
        easy to remove, so this is reversible.

        The response reports the resolved effect display names, the per-clip
        apply results, and any labels that could not be matched. This does NOT
        run Premiere's "Enhance Speech" (no UXP API) — it applies the standard
        DeNoise/DeReverb audio effects. Verify the result by ear in Premiere.
        """
        labels = effect_labels or DEFAULT_AUDIO_CLEANUP

        available = _unwrap(get_audio_effect_names()).get("effects", []) or []
        lower_available = [(name, name.lower()) for name in available]

        resolved = []
        unmatched = []
        for label in labels:
            needle = label.lower()
            # Match precedence: exact, then prefix, then the requested label is a
            # substring of an available name. We deliberately DO NOT match when an
            # available name is a substring of the requested label — that turned
            # "DeReverb" into "Reverb", the OPPOSITE effect.
            match = (
                next((name for name, low in lower_available if low == needle), None)
                or next((name for name, low in lower_available if low.startswith(needle)), None)
                or next((name for name, low in lower_available if needle in low), None)
            )
            if match:
                resolved.append(match)
            else:
                unmatched.append(label)

        layout = _unwrap(get_sequence_layout(sequence_id))
        audio_tracks = layout.get("audioTracks", []) or []

        applied = []
        errors = []
        clip_count = 0
        for track in audio_tracks:
            t_index = track.get("index")
            if audio_track_index is not None and t_index != audio_track_index:
                continue
            for clip in track.get("tracks", []) or []:
                clip_count += 1
                c_index = clip.get("index")
                for effect_name in resolved:
                    try:
                        add_audio_effect(sequence_id, t_index, c_index, effect_name)
                        applied.append(
                            {
                                "audioTrackIndex": t_index,
                                "clipIndex": c_index,
                                "effect": effect_name,
                            }
                        )
                    except Exception as exc:  # report, do not abort the batch
                        errors.append(
                            {
                                "audioTrackIndex": t_index,
                                "clipIndex": c_index,
                                "effect": effect_name,
                                "error": str(exc),
                            }
                        )

        return {
            "action": "clean_audio_pipeline",
            "requestedLabels": labels,
            "resolvedEffects": resolved,
            "unmatchedLabels": unmatched,
            "availableAudioEffects": available,
            "audioClipCount": clip_count,
            "appliedCount": len(applied),
            "applied": applied,
            "errors": errors,
            "note": (
                "Audio effects added but not verified by playback. "
                "Confirm the result by ear in Premiere."
            ),
        }


def create_premiere_tools_server(name: str = "Premiere Tools") -> FastMCP:
    """Create a standalone MCP server with the additional Premiere tools."""
    mcp = FastMCP(name, log_level="ERROR")
    register_tools(mcp)
    return mcp
