---
last_verified: 2026-06-13
---

# Premiere Workflow Memory

This repo exists to edit inside Adobe Premiere Pro through Adobe MCP.

## Source Of Truth

The live Premiere sequence is the source of truth. Do not replace it with a
Python-rendered assembly, proxy timeline, or generated alternate sequence unless
the user explicitly asks for that path.

## Active Workspace

- Active app: `apps/premiere`
- MCP server and UXP bridge: `apps/premiere/adobe-mcp`
- ExtendScripts: `apps/premiere/scripts`
- Repo workflow skills: `apps/premiere/skills`
- The old self-editing Python app has been removed from the working tree.

## Cutting Contract

- Use `remove_silence_segments` for transcript-based removals.
- Provide removal ranges in source timeline seconds.
- Let the tool process cuts end-to-start.
- Verify the active sequence after each batch using project or clip inspection.
- Treat success responses as untrusted until the timeline actually changed.

## Hard Stops

Stop and report status if:

- the active sequence is not the requested sequence
- Premiere focus or keyboard automation is uncertain
- a cut reports success but the timeline layout is unchanged
- a fallback would use unsafe split/delete/trim APIs
- a fallback would create a new timeline, rendered file, or replacement assembly

## Unsafe For This Workflow

- `split_video_clip`
- `split_audio_clip`
- `remove_linked_clip_range`
- `batch_split_clips`
- `cut_at_playhead`
- `trim_video_clip`
- `trim_audio_clip`
- `set_clip_position`
