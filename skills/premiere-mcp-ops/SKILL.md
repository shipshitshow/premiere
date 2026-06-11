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
- Cut only the existing sequence requested by the user. Do not create alternate
  sequences, rendered assemblies, proxy files, or API-built replacement timelines
  unless the user explicitly asks for that.
- Treat `remove_silence_segments` success as untrusted until verified against the
  actual clip layout with `get_full_project_data` or equivalent sequence/clip
  inspection.
- If the tool reports success but the target sequence did not change, stop and
  report a Premiere focus / keyboard automation problem. Do not invent a fallback
  edit strategy inside the live project.
- Do not use `set_clip_position` to close gaps. It can stretch/expand clips rather
  than move them safely.
- If gaps remain after a successful cut and no documented safe gap-closing method
  is available, stop and tell the user the cuts are done and gaps need manual
  packing.

Unsafe tools for this workflow:

- `split_video_clip`
- `split_audio_clip`
- `remove_linked_clip_range`
- `batch_split_clips`
- `cut_at_playhead`
- `trim_video_clip`
- `trim_audio_clip`
- `set_clip_position`

## Verification Contract

After each cut batch:

1. Inspect the target sequence with `get_full_project_data`, `get_sequence_settings`,
   or clip-level inspection.
2. Confirm the target sequence name/id is still the one the user requested.
3. Confirm clip count, clip starts/ends, or sequence duration actually changed.
4. If the tool returned success but the target sequence layout is unchanged, treat
   the operation as failed.
5. Report the verified state in plain terms before continuing.

Do not trust MCP success responses alone.

## Gap Handling

`remove_silence_segments` may leave kept clips separated by gaps depending on
Premiere focus, command mapping, and Timeline state.

- Do not close gaps with `set_clip_position`; it can stretch/expand clips.
- Do not close gaps with split/trim/delete fallback APIs.
- Only close gaps if there is a documented, verified-safe Premiere workflow for the
  current project state.
- If no safe gap-closing method is verified, stop after cutting and tell the user:
  "Cuts are done; gaps remain for manual packing."

## Never Create Unless Explicitly Asked

Do not create:

- alternate edit sequences
- duplicate target sequences
- rendered MP4 assemblies
- FFmpeg proxy cuts
- API-built replacement timelines
- temporary media intended to replace the Premiere timeline

If a recovery path requires any of the above, stop and ask the user first.

## Hard Stop Conditions

Stop immediately if any of these happen:

- The active sequence is not the sequence the user named.
- `remove_silence_segments` reports success but the target sequence did not change.
- AppleScript / keyboard automation is denied, times out, or appears to hit the
  wrong Premiere panel.
- A proposed fallback would use an unsafe tool listed above.
- A proposed fallback would create a new timeline or rendered file.
- A verification step shows clips stretched, desynced, duplicated unexpectedly, or
  otherwise changed outside the approved removal ranges.

When stopped, give the user the exact sequence name/id, what changed, what did not
change, and the next manual action needed.

## Recovery

If the connection drops or cuts partially apply:

1. Re-check proxy connectivity.
2. Reconnect the UXP plugin if needed.
3. Inspect project/sequence state.
4. Determine which removal ranges are still pending.
5. Resume with only the remaining ranges.

If a fallback would require creating a new sequence, rendering a cut, cloning
clips manually, or using lower-level clip mutation APIs, do not proceed. Ask the
user or stop with a clear status.

## Collaboration Rules

- Planning and execution are separate steps.
- If the user asks for a timeline plan only, do not execute.
- If the user asks to cut now, use the approved removal ranges directly.

## References

Read these only if needed:

- `mcp/premiere-python-mcp/WORKFLOW.md`
- `mcp/adobe-premiere-mcp/PREMIERE_PIPELINE_SETUP.md`
