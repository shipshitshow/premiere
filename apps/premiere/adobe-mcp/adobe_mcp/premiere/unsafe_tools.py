"""MCP tools that must not be registered.

These UXP/keystroke helpers still exist as Python functions for reference,
but they are not exposed to agents. The 2026-06-11 cut failure happened
because an agent used split/trim/delete/`set_clip_position` instead of
`remove_silence_segments`.
"""

# Canonical unregistered surface. Keep in sync with server.py (no @mcp.tool).
UNREGISTERED_UNSAFE_TOOLS = (
    "split_video_clip",
    "split_audio_clip",
    "split_clip_at_time",
    "batch_split_clips",
    "trim_video_clip",
    "trim_audio_clip",
    "remove_video_clip_range",
    "remove_linked_clip_range",
    "remove_clips",
    "delete_clip",
    "cut_at_playhead",
    "ripple_delete",
    "set_clip_position",
    "send_keystroke",
    "delete_selected",
    "move_clip",
)
