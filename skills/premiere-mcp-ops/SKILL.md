---
name: premiere-mcp-ops
description: Safely operate this repo's adobe-premiere-mcp workflow. Use when the user wants to verify the Premiere bridge, execute transcript-based cuts, recover from partial failures, or work directly against the active Premiere sequence.
---

# Premiere MCP Ops

Use this skill for the fragile, repo-specific Premiere control path.

## Preconditions

Before any cut execution, confirm:

- proxy server is running on `localhost:3001`
- Premiere is connected to the proxy
- the active sequence exists
- Premiere is the frontmost window

If MCP tools are not exposed in the session, say that plainly. Do not pretend the edit was applied.

## Cutting Rules

- Use `remove_silence_segments` only for transcript-based removal ranges.
- Do not use split/delete combinations that can desync video and audio.
- Provide removal segments in source timeline seconds.
- Let the tool process end-to-start.

Unsafe tools for this workflow:

- `split_video_clip`
- `split_audio_clip`
- `remove_linked_clip_range`
- `batch_split_clips`
- `cut_at_playhead`

## Recovery

If the connection drops or cuts partially apply:

1. Re-check proxy connectivity.
2. Reconnect the UXP plugin if needed.
3. Inspect project/sequence state.
4. Determine which removal ranges are still pending.
5. Resume with only the remaining ranges.

## Collaboration Rules

- Planning and execution are separate steps.
- If the user asks for a timeline plan only, do not execute.
- If the user asks to cut now, use the approved removal ranges directly.

## References

Read these only if needed:

- `mcp/premiere-python-mcp/WORKFLOW.md`
- `mcp/adobe-premiere-mcp/PREMIERE_PIPELINE_SETUP.md`
